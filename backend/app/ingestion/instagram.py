"""
Instagram Graph API ingestion -- a third real ingestion connector, same
architecture as news.py and youtube.py.

DORMANT until real credentials exist: requires INSTAGRAM_ACCESS_TOKEN
and INSTAGRAM_BUSINESS_ACCOUNT_ID (the IG User ID of *our* linked
Business/Creator account -- required by the API as the querying
identity, even to read public content). Getting these requires an
Instagram Business account, a linked Facebook Page, a Meta Developer
app, Business Verification, and App Review for the "Instagram Public
Content Access" feature -- see CLAUDE.md for the full walkthrough. None
of that can be done from this codebase.

IMPORTANT: unlike youtube.py, this connector has NOT been exercised
against the live Instagram Graph API -- there was no token available to
test with. Endpoint paths/params (ig_hashtag_search, recent_media,
business_discovery) were sourced from current Meta developer
documentation, but should be smoke-tested carefully (same way youtube.py
was verified against real data before shipping) the moment
INSTAGRAM_ACCESS_TOKEN is actually set -- treat the first real run as a
verification pass, not a known-good deploy.

Two lanes, mirroring youtube.py's official/community split:

1. Official account (source_trust_tier='official'): Business Discovery
   on Pop Mart's global handle (@popmart) -- GET /{our-ig-user-id}?
   fields=business_discovery.username(popmart){media{...}}. Only
   returns data if @popmart is itself a Business/Creator account, which
   is the normal case for a brand account.
2. Hashtag search (source_trust_tier='community'): a small, fixed
   hashtag list covering unboxing/box-opening content, matching
   youtube.py's search scope.

Hashtag ID resolution (ig_hashtag_search) is capped at 30 unique
hashtags per rolling 7 days per IG business account. Resolved IDs are
cached in the instagram_hashtag_cache table (persisted, not just
in-memory) so redeploys don't silently re-burn that quota re-resolving
the same hashtags on every restart -- recent_media lookups against an
already-resolved hashtag ID are NOT subject to that cap and run every
poll.

Card type: 'video', per FEED_SYSTEM_DESIGN.md's taxonomy ("Instagram
Reels" is explicitly listed under the 🎥 Videos card type). Only
VIDEO media_type results are kept -- IMAGE/CAROUSEL_ALBUM posts are
skipped, since there's no documented card type for ingested photo
content.

Note: recent_media's response cannot include a `username` field (a
documented Graph API restriction), so ingested community-tier posts
have no attributable poster -- same posture as news.py's ingested
articles.
"""
import asyncio
import html
import logging
import os
import time
from datetime import datetime, timezone

import httpx

from backend.app.db.database import get_connection
from backend.app.ingestion.common import load_catalog, resolve_title
from backend.app.notifications.service import notify_followers_of_new_card

_log = logging.getLogger(__name__)

_API_BASE = "https://graph.facebook.com/v22.0"
_OFFICIAL_ACCOUNT_USERNAME = "popmart"

# Kept short and fixed -- ig_hashtag_search's 30-per-7-days cap makes an
# open-ended or user-configurable hashtag list risky.
_HASHTAGS = ["popmart", "popmartunboxing", "popmartlabubu"]

DEFAULT_INTERVAL_SECONDS = 7200  # 2 hours, same cadence as youtube.py


def _parse_timestamp(value: str | None) -> int:
    if not value:
        return int(time.time())
    try:
        return int(datetime.fromisoformat(value).astimezone(timezone.utc).timestamp())
    except ValueError:
        return int(time.time())


def _required_env() -> tuple[str, str] | None:
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    business_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    if not token or not business_id:
        return None
    return token, business_id


async def _get_json(client: httpx.AsyncClient, path: str, params: dict) -> dict:
    resp = await client.get(f"{_API_BASE}/{path}", params=params)
    resp.raise_for_status()
    return resp.json()


def _extract_video(media: dict) -> dict | None:
    if media.get("media_type") != "VIDEO":
        return None
    media_id = media.get("id")
    if not media_id:
        return None
    caption = media.get("caption") or ""
    return {
        "media_id": media_id,
        "title": html.unescape(caption)[:200] or "Instagram video",
        "published_at": _parse_timestamp(media.get("timestamp")),
    }


async def _fetch_official_videos(client: httpx.AsyncClient, token: str, business_id: str) -> list[dict]:
    try:
        data = await _get_json(
            client,
            business_id,
            {
                "fields": (
                    f"business_discovery.username({_OFFICIAL_ACCOUNT_USERNAME})"
                    "{media{id,caption,media_type,timestamp}}"
                ),
                "access_token": token,
            },
        )
        media_items = ((data.get("business_discovery") or {}).get("media") or {}).get("data") or []
    except Exception:
        _log.warning("instagram ingestion: official account fetch failed, skipping", exc_info=True)
        return []

    videos = []
    for m in media_items:
        v = _extract_video(m)
        if v:
            v["trust_tier"] = "official"
            videos.append(v)
    return videos


def _cached_hashtag_id(conn, hashtag: str) -> str | None:
    row = conn.execute(
        "SELECT hashtag_id FROM instagram_hashtag_cache WHERE hashtag = ?", (hashtag,)
    ).fetchone()
    return row["hashtag_id"] if row else None


def _cache_hashtag_id(conn, hashtag: str, hashtag_id: str) -> None:
    conn.execute(
        "INSERT INTO instagram_hashtag_cache (hashtag, hashtag_id, resolved_at) VALUES (?, ?, ?) "
        "ON CONFLICT(hashtag) DO UPDATE SET hashtag_id = excluded.hashtag_id, resolved_at = excluded.resolved_at",
        (hashtag, hashtag_id, int(time.time())),
    )
    conn.commit()


async def _resolve_hashtag_id(client: httpx.AsyncClient, token: str, business_id: str, hashtag: str) -> str | None:
    conn = get_connection()
    try:
        cached = _cached_hashtag_id(conn, hashtag)
    finally:
        conn.close()
    if cached:
        return cached

    try:
        data = await _get_json(
            client, "ig_hashtag_search", {"user_id": business_id, "q": hashtag, "access_token": token}
        )
        items = data.get("data") or []
        if not items:
            return None
        hashtag_id = items[0]["id"]
    except Exception:
        _log.warning("instagram ingestion: hashtag resolve failed", extra={"hashtag": hashtag}, exc_info=True)
        return None

    conn = get_connection()
    try:
        _cache_hashtag_id(conn, hashtag, hashtag_id)
    finally:
        conn.close()
    return hashtag_id


async def _fetch_hashtag_videos(client: httpx.AsyncClient, token: str, business_id: str) -> list[dict]:
    videos = []
    for hashtag in _HASHTAGS:
        hashtag_id = await _resolve_hashtag_id(client, token, business_id, hashtag)
        if not hashtag_id:
            continue
        try:
            data = await _get_json(
                client,
                f"{hashtag_id}/recent_media",
                {"user_id": business_id, "fields": "id,caption,media_type,timestamp", "access_token": token},
            )
        except Exception:
            _log.warning("instagram ingestion: recent_media fetch failed", extra={"hashtag": hashtag}, exc_info=True)
            continue

        for m in data.get("data") or []:
            v = _extract_video(m)
            if v:
                v["trust_tier"] = "community"
                videos.append(v)
    return videos


async def ingest_instagram_videos() -> int:
    """No-op (returns 0, fetches nothing) if INSTAGRAM_ACCESS_TOKEN /
    INSTAGRAM_BUSINESS_ACCOUNT_ID aren't set -- real code, not a stub,
    just inactive without real credentials. Same two-phase
    read-catalog / fetch-over-network / write shape as news.py and
    youtube.py, so a slow batch of API calls never holds a DB write
    lock other requests are waiting on."""
    creds = _required_env()
    if not creds:
        return 0
    token, business_id = creds

    read_conn = get_connection()
    try:
        series, figures = load_catalog(read_conn)
    finally:
        read_conn.close()

    async with httpx.AsyncClient(timeout=10) as client:
        official_videos = await _fetch_official_videos(client, token, business_id)
        hashtag_videos = await _fetch_hashtag_videos(client, token, business_id)

    # Official wins any media_id collision, same tie-break as youtube.py.
    by_id: dict[str, dict] = {v["media_id"]: v for v in hashtag_videos}
    by_id.update({v["media_id"]: v for v in official_videos})

    to_insert = []
    for video in by_id.values():
        figure_id, series_id = resolve_title(video["title"], series, figures)
        body = (
            "New video from the official Pop Mart account."
            if video["trust_tier"] == "official"
            else "New video tagged with a Pop Mart hashtag."
        )
        to_insert.append((
            f"ig:{video['media_id']}",
            figure_id,
            series_id,
            video["title"],
            body,
            video["trust_tier"],
            video["published_at"],
        ))

    inserted = 0
    newly_inserted: list[tuple[str, str | None, str]] = []
    write_conn = get_connection()
    try:
        for external_id, figure_id, series_id, title, body, trust_tier, created_at in to_insert:
            cur = write_conn.execute(
                "INSERT OR IGNORE INTO feed_cards "
                "(id, card_type, figure_id, series_id, title, body, source_trust_tier, "
                "region, external_id, created_at) "
                "VALUES (?, 'video', ?, ?, ?, ?, ?, 'Global', ?, ?)",
                (external_id, figure_id, series_id, title, body, trust_tier, external_id, created_at),
            )
            if cur.rowcount:
                inserted += 1
                newly_inserted.append((external_id, series_id, title))
        write_conn.commit()
    finally:
        write_conn.close()

    for card_id, series_id, title in newly_inserted:
        notify_followers_of_new_card(card_id, series_id, title)

    return inserted


async def run_instagram_ingestion_loop(interval_seconds: int = DEFAULT_INTERVAL_SECONDS) -> None:
    """Background loop: ingest immediately, then every `interval_seconds`.
    Never raises -- a failed pass is logged and the loop keeps going."""
    while True:
        try:
            count = await ingest_instagram_videos()
            _log.info("instagram ingestion pass complete: %d new card(s)", count)
        except Exception:
            _log.exception("instagram ingestion pass failed")
        await asyncio.sleep(interval_seconds)
