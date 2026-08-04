"""
YouTube Data API v3 ingestion — a second real ingestion source, alongside
news.py's Google News RSS connector.

Two lanes, mirroring TREND_DETECTION_DESIGN.md's Trust Tiers:

1. Official channel uploads (source_trust_tier='official'): resolved once
   per pass via channels.list?forHandle=POPMARTOFFICIAL, then fetched via
   playlistItems.list against that channel's uploads playlist. Costs ~2
   quota units per pass -- playlistItems.list is far cheaper than search.
2. Community search hits (source_trust_tier='community', same tier as
   news.py's ingested articles -- we can't independently verify a random
   search result's uploader is an actually-known collector creator, which
   is what 'verified_creator' would claim): a handful of fixed queries
   covering unboxings/box-openings and new-release promotions, per the
   user's explicit scope. search.list costs 100 quota units per query.

Quota budget: the YouTube Data API's free daily quota is 10,000 units.
With _SEARCH_QUERIES below (4 queries = 400 units) + the official-channel
lookup (~2 units) = ~402 units per pass. DEFAULT_INTERVAL_SECONDS is set
to keep total daily usage comfortably under budget with margin for other
usage of the same key (12 passes/day * 402 =~ 4,824 units/day).

Card type: 'video', per FEED_SYSTEM_DESIGN.md's card taxonomy ("🎥 Videos
| Ingestion (TikTok / YouTube Shorts / Instagram Reels) | Short-form
content discussing figures").

Requires YOUTUBE_API_KEY. If unset, run_youtube_ingestion_loop() is never
started (see main.py) -- no fake/stub data, this connector simply does
nothing until a real key is configured, same posture as OPENAI_API_KEY
elsewhere in this project.
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

_API_BASE = "https://www.googleapis.com/youtube/v3"
_OFFICIAL_CHANNEL_HANDLE = "POPMARTOFFICIAL"

# Fixed queries covering exactly what was asked for: unboxings/box-openings
# and promotional/new-release content. Kept short (4 queries) to stay
# inside the free daily quota -- see module docstring for the math.
_SEARCH_QUERIES = [
    "Pop Mart unboxing",
    "Pop Mart box opening",
    "Pop Mart Labubu",
    "Pop Mart new release",
]

DEFAULT_INTERVAL_SECONDS = 7200  # 2 hours


def _parse_published_at(value: str | None) -> int:
    if not value:
        return int(time.time())
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp())
    except ValueError:
        return int(time.time())


async def _get_json(client: httpx.AsyncClient, path: str, params: dict) -> dict:
    resp = await client.get(f"{_API_BASE}/{path}", params=params)
    resp.raise_for_status()
    return resp.json()


async def _fetch_official_uploads(client: httpx.AsyncClient, api_key: str) -> list[dict]:
    """Resolves the official channel's uploads playlist and returns its
    most recent videos. Returns [] (never raises) on any failure -- a
    wrong/renamed handle or a transient API error shouldn't take down the
    whole ingestion pass, same posture as news.py's per-query try/except."""
    try:
        channel_data = await _get_json(
            client,
            "channels",
            {"part": "contentDetails", "forHandle": _OFFICIAL_CHANNEL_HANDLE, "key": api_key},
        )
        items = channel_data.get("items") or []
        if not items:
            return []
        uploads_playlist_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

        playlist_data = await _get_json(
            client,
            "playlistItems",
            {"part": "snippet,contentDetails", "playlistId": uploads_playlist_id, "maxResults": 10, "key": api_key},
        )
    except Exception:
        _log.warning("youtube ingestion: official channel fetch failed, skipping", exc_info=True)
        return []

    videos = []
    for item in playlist_data.get("items") or []:
        snippet = item.get("snippet") or {}
        content = item.get("contentDetails") or {}
        video_id = content.get("videoId")
        if not video_id or not snippet.get("title"):
            continue
        videos.append({
            "video_id": video_id,
            "title": html.unescape(snippet["title"])[:200],
            "channel_title": snippet.get("channelTitle") or "POP MART",
            "published_at": _parse_published_at(content.get("videoPublishedAt") or snippet.get("publishedAt")),
            "trust_tier": "official",
        })
    return videos


async def _fetch_search_videos(client: httpx.AsyncClient, api_key: str) -> list[dict]:
    videos = []
    for query in _SEARCH_QUERIES:
        try:
            data = await _get_json(
                client,
                "search",
                {"part": "snippet", "q": query, "type": "video", "order": "date", "maxResults": 10, "key": api_key},
            )
        except Exception:
            _log.warning("youtube ingestion: search query failed, skipping", extra={"query": query}, exc_info=True)
            continue

        for item in data.get("items") or []:
            video_id = (item.get("id") or {}).get("videoId")
            snippet = item.get("snippet") or {}
            if not video_id or not snippet.get("title"):
                continue
            videos.append({
                "video_id": video_id,
                "title": html.unescape(snippet["title"])[:200],
                "channel_title": snippet.get("channelTitle") or "YouTube",
                "published_at": _parse_published_at(snippet.get("publishedAt")),
                "trust_tier": "community",
            })
    return videos


async def ingest_youtube_videos() -> int:
    """Fetches official-channel uploads + search results and inserts new
    ones as 'video' feed cards. Returns the count of newly-inserted cards.
    Already-seen videos (matched by video_id, doubled as external_id) are
    silently skipped via INSERT OR IGNORE. No-op (returns 0) if
    YOUTUBE_API_KEY isn't set.

    Same two-phase shape as news.py's ingest_google_news(): all network
    fetching happens before any DB connection is opened, so a slow batch
    of API calls never holds a write lock other concurrent requests are
    waiting on."""
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        return 0

    read_conn = get_connection()
    try:
        series, figures = load_catalog(read_conn)
    finally:
        read_conn.close()

    async with httpx.AsyncClient(timeout=10) as client:
        official_videos = await _fetch_official_uploads(client, api_key)
        search_videos = await _fetch_search_videos(client, api_key)

    # Official-channel videos win any video_id collision (shouldn't happen
    # in practice, but if it did, 'official' is the more trustworthy tier).
    by_id: dict[str, dict] = {v["video_id"]: v for v in search_videos}
    by_id.update({v["video_id"]: v for v in official_videos})

    to_insert = []
    for video in by_id.values():
        figure_id, series_id = resolve_title(video["title"], series, figures)
        body = f"New video from {video['channel_title']}."
        to_insert.append((
            f"yt:{video['video_id']}",
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


async def run_youtube_ingestion_loop(interval_seconds: int = DEFAULT_INTERVAL_SECONDS) -> None:
    """Background loop: ingest immediately, then every `interval_seconds`.
    Never raises -- a failed pass is logged and the loop keeps going."""
    while True:
        try:
            count = await ingest_youtube_videos()
            _log.info("youtube ingestion pass complete: %d new card(s)", count)
        except Exception:
            _log.exception("youtube ingestion pass failed")
        await asyncio.sleep(interval_seconds)
