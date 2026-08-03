"""
Google News RSS ingestion — the real, working ingestion source for now.

Reddit's public JSON endpoints (the originally planned first connector) are
hard-blocked by bot-protection for datacenter/cloud IPs regardless of
User-Agent — confirmed from the dev sandbox with a 403 "Blocked" challenge
page on every request. That's an IP-class block (Akamai-style), not a
UA/rate-limit issue, so it would very likely fail identically from Railway.
Google News RSS needs no API key/auth and isn't blocked the same way, so
it's the real v1 connector. TikTok/Instagram/YouTube/Xiaohongshu/Weibo/X/
official Pop Mart connectors described in TREND_DETECTION_DESIGN.md remain
stubs pending real platform API access.

Caveat: Google News's RSS terms restrict use to personal, non-commercial,
feed-reader purposes. Fine for this MVP/demo stage — swap for a licensed
news API (or the real social connectors) before treating this as a
commercial data source.
"""
import asyncio
import html
import logging
import re
import time
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import httpx

from backend.app.db.database import get_connection
from backend.app.notifications.service import notify_followers_of_new_card

_log = logging.getLogger(__name__)

_USER_AGENT = "Mozilla/5.0 (compatible; poop-mart-ingestion/0.1; +https://github.com/flyingabove/poop_mart)"

# One query per brand line we track, plus a general catch-all — mirrors the
# series catalog in db/seed.py so ingested news lines up with what the app
# already knows about.
_QUERIES = [
    "Pop Mart Labubu",
    "Pop Mart Crybaby",
    "Pop Mart Skullpanda",
    "Pop Mart Molly figure",
    "Pop Mart Dimoo",
    "Pop Mart blind box",
]

DEFAULT_INTERVAL_SECONDS = 600  # 10 minutes — polite polling cadence

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(text: str) -> str:
    return html.unescape(_TAG_RE.sub("", text or "")).strip()


async def _fetch_rss(query: str) -> str:
    url = "https://news.google.com/rss/search"
    params = {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params, headers={"User-Agent": _USER_AGENT})
        resp.raise_for_status()
        return resp.text


def _parse_items(xml_text: str) -> list[dict]:
    root = ElementTree.fromstring(xml_text)
    items = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or link).strip()
        pub_date = item.findtext("pubDate")
        source_el = item.find("source")
        source_name = source_el.text.strip() if source_el is not None and source_el.text else None

        created_at = int(time.time())
        if pub_date:
            try:
                created_at = int(parsedate_to_datetime(pub_date).timestamp())
            except (TypeError, ValueError):
                pass

        if not title or not guid:
            continue
        items.append({
            "external_id": f"gnews:{guid}",
            "title": _strip_tags(title)[:200],
            "source_name": source_name,
            "url": link,
            "created_at": created_at,
        })
    return items


def _load_catalog(conn) -> tuple[list[dict], list[dict]]:
    series = [dict(r) for r in conn.execute("SELECT id, name, aliases FROM series")]
    figures = [dict(r) for r in conn.execute("SELECT id, name, series_id FROM figures")]
    return series, figures


def _resolve(title: str, series: list[dict], figures: list[dict]) -> tuple[str | None, str | None]:
    """Best-effort match a headline to a known figure/series by substring —
    the same alias-table resolution approach described in
    TREND_DETECTION_DESIGN.md, just without a real NLP layer yet.

    Leaves both None rather than guessing when nothing matches: an unlinked
    news card still renders fine in the feed, a wrongly-linked one actively
    misleads whoever reads it on a figure's page.
    """
    t = title.lower()
    for fig in figures:
        if fig["name"].lower() in t:
            return fig["id"], fig["series_id"]
    for s in series:
        aliases = [a.strip().lower() for a in (s["aliases"] or "").split(",") if a.strip()]
        if any(name in t for name in [s["name"].lower(), *aliases]):
            return None, s["id"]
    return None, None


async def ingest_google_news() -> int:
    """Fetch every tracked query and insert new articles as feed cards.

    Returns the count of newly-inserted cards. Already-seen articles
    (matched by external_id, which doubles as the row's primary key) are
    silently skipped via INSERT OR IGNORE — re-polling the same headline is
    a no-op, not a duplicate.

    Network fetching and DB writing are deliberately two separate phases —
    no DB connection is held open across the network round-trips. An
    earlier version opened one connection, then looped `await
    _fetch_rss(query)` for all 6 queries with writes interleaved in
    between, only committing at the end. That transaction could stay open
    for 10-30+ seconds across six sequential HTTP round-trips to Google
    News — long enough that any other concurrent write anywhere in the app
    (a signup, a review, a vote) could hit "database is locked" waiting
    for it. Fetching everything first, then opening a connection only to
    do the (fast, local) INSERTs, shrinks the write-lock window to
    however long the INSERTs themselves take.
    """
    read_conn = get_connection()
    try:
        series, figures = _load_catalog(read_conn)
    finally:
        read_conn.close()

    to_insert: list[tuple[str, str | None, str | None, str, str, int]] = []
    for query in _QUERIES:
        try:
            xml_text = await _fetch_rss(query)
            items = _parse_items(xml_text)
        except Exception:
            _log.warning("ingestion: query failed, skipping", extra={"query": query}, exc_info=True)
            continue

        for item in items:
            figure_id, series_id = _resolve(item["title"], series, figures)
            body = f"Covered by {item['source_name']}." if item["source_name"] else "Covered in the press."
            to_insert.append(
                (item["external_id"], figure_id, series_id, item["title"], body, item["created_at"])
            )

    inserted = 0
    newly_inserted: list[tuple[str, str | None, str]] = []  # (card_id, series_id, title)
    write_conn = get_connection()
    try:
        for external_id, figure_id, series_id, title, body, created_at in to_insert:
            cur = write_conn.execute(
                "INSERT OR IGNORE INTO feed_cards "
                "(id, card_type, figure_id, series_id, title, body, source_trust_tier, "
                "region, external_id, created_at) "
                "VALUES (?, 'regional_news', ?, ?, ?, ?, 'community', 'Global', ?, ?)",
                (external_id, figure_id, series_id, title, body, external_id, created_at),
            )
            if cur.rowcount:
                inserted += 1
                newly_inserted.append((external_id, series_id, title))
        write_conn.commit()
    finally:
        write_conn.close()

    # Notify after commit, on a separate connection, so a notification never
    # references a feed card that isn't durably visible yet.
    for card_id, series_id, title in newly_inserted:
        notify_followers_of_new_card(card_id, series_id, title)

    return inserted


async def run_ingestion_loop(interval_seconds: int = DEFAULT_INTERVAL_SECONDS) -> None:
    """Background loop: ingest immediately, then every `interval_seconds`.

    Never raises — a failed pass is logged and the loop keeps going, so one
    bad network blip doesn't take down the whole app.
    """
    while True:
        try:
            count = await ingest_google_news()
            _log.info("ingestion pass complete: %d new card(s)", count)
        except Exception:
            _log.exception("ingestion pass failed")
        await asyncio.sleep(interval_seconds)
