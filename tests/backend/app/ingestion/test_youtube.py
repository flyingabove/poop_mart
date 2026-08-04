import asyncio

import pytest

from backend.app.db import database as db_module
from backend.app.ingestion import youtube as yt_mod

_CHANNELS_RESPONSE = {
    "items": [
        {"id": "UCofficial123", "contentDetails": {"relatedPlaylists": {"uploads": "UUofficial123"}}}
    ]
}

_PLAYLIST_ITEMS_RESPONSE = {
    "items": [
        {
            "contentDetails": {"videoId": "official-vid-1", "videoPublishedAt": "2026-08-01T12:00:00Z"},
            "snippet": {"title": "POP MART Labubu Official Unboxing", "channelTitle": "POP MART"},
        }
    ]
}


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class _FakeYoutubeClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, params=None, headers=None):
        if url.endswith("/channels"):
            return _FakeResponse(_CHANNELS_RESPONSE)
        if url.endswith("/playlistItems"):
            return _FakeResponse(_PLAYLIST_ITEMS_RESPONSE)
        if url.endswith("/search"):
            query = params["q"]
            video_id = f"search-{abs(hash(query))}"
            return _FakeResponse({
                "items": [
                    {
                        "id": {"videoId": video_id},
                        "snippet": {
                            "title": f"Fan video about {query}",
                            "channelTitle": "Fan Channel",
                            "publishedAt": "2026-08-01T12:00:00Z",
                        },
                    }
                ]
            })
        raise AssertionError(f"unexpected YouTube API url in test: {url}")


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    db_module.init_db()
    yield


def test_ingest_noop_without_api_key(isolated_db, monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.setattr(yt_mod.httpx, "AsyncClient", _FakeYoutubeClient)

    count = asyncio.run(yt_mod.ingest_youtube_videos())
    assert count == 0

    conn = db_module.get_connection()
    rows = conn.execute("SELECT * FROM feed_cards WHERE card_type = 'video'").fetchall()
    conn.close()
    assert rows == []


def test_ingest_inserts_official_and_search_videos_and_dedupes(isolated_db, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setattr(yt_mod.httpx, "AsyncClient", _FakeYoutubeClient)

    first = asyncio.run(yt_mod.ingest_youtube_videos())
    assert first == 1 + len(yt_mod._SEARCH_QUERIES)  # 1 official upload + 1 per search query

    second = asyncio.run(yt_mod.ingest_youtube_videos())
    assert second == 0  # same video ids on re-poll -> nothing new


def test_official_channel_video_is_tagged_official_tier(isolated_db, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setattr(yt_mod.httpx, "AsyncClient", _FakeYoutubeClient)

    asyncio.run(yt_mod.ingest_youtube_videos())

    conn = db_module.get_connection()
    row = conn.execute("SELECT * FROM feed_cards WHERE id = 'yt:official-vid-1'").fetchone()
    conn.close()
    assert row is not None
    assert row["source_trust_tier"] == "official"
    assert row["card_type"] == "video"


def test_search_result_video_is_tagged_community_tier(isolated_db, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setattr(yt_mod.httpx, "AsyncClient", _FakeYoutubeClient)

    asyncio.run(yt_mod.ingest_youtube_videos())

    conn = db_module.get_connection()
    rows = conn.execute(
        "SELECT * FROM feed_cards WHERE card_type = 'video' AND source_trust_tier = 'community'"
    ).fetchall()
    conn.close()
    assert len(rows) == len(yt_mod._SEARCH_QUERIES)


def test_ingest_notifies_followers_of_resolved_series(isolated_db, monkeypatch):
    """End-to-end: ingest -> resolve a video title to a series -> notify
    anyone following it. The fake client's "Pop Mart Labubu" query produces
    a title containing "labubu", which should resolve via the series alias
    -- same shape as news.py's equivalent test."""
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setattr(yt_mod.httpx, "AsyncClient", _FakeYoutubeClient)

    conn = db_module.get_connection()
    conn.execute(
        "INSERT INTO series (id, name, aliases, brand_line, release_date, regions) VALUES (?, ?, ?, ?, ?, ?)",
        ("labubu-forest-party", "Labubu Forest Party", "labubu", "Labubu", "2026-01-01", "Global"),
    )
    conn.execute(
        "INSERT INTO users (id, email, password_salt, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
        ("user-1", "watcher@example.com", "salt", "hash", 0),
    )
    conn.execute(
        "INSERT INTO series_follows (user_id, series_id, created_at) VALUES (?, ?, ?)",
        ("user-1", "labubu-forest-party", 0),
    )
    conn.commit()
    conn.close()

    asyncio.run(yt_mod.ingest_youtube_videos())

    conn = db_module.get_connection()
    notifs = conn.execute("SELECT * FROM notifications WHERE user_id = ?", ("user-1",)).fetchall()
    conn.close()

    # Both the official upload ("POP MART Labubu Official Unboxing") and the
    # "Pop Mart Labubu" search query's result title contain "labubu" -- two
    # matching videos, two notifications.
    assert len(notifs) == 2
    assert all(n["series_id"] == "labubu-forest-party" for n in notifs)


def test_title_html_entities_are_unescaped(isolated_db, monkeypatch):
    # Real YouTube API responses can return titles with HTML entities
    # (e.g. "POP MART &amp; MYSTERY EGGS") -- confirmed against the live
    # API, not hypothetical. Reuses the same html.unescape() treatment
    # news.py's _strip_tags() already applies to RSS titles.
    class _EntityTitleClient(_FakeYoutubeClient):
        async def get(self, url, params=None, headers=None):
            if url.endswith("/channels"):
                return _FakeResponse(_CHANNELS_RESPONSE)
            if url.endswith("/playlistItems"):
                return _FakeResponse({
                    "items": [{
                        "contentDetails": {"videoId": "entity-vid-1", "videoPublishedAt": "2026-08-01T12:00:00Z"},
                        "snippet": {"title": "POP MART &amp; MYSTERY EGGS", "channelTitle": "POP MART"},
                    }]
                })
            if url.endswith("/search"):
                return _FakeResponse({"items": []})
            raise AssertionError(f"unexpected url {url}")

    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setattr(yt_mod.httpx, "AsyncClient", _EntityTitleClient)

    asyncio.run(yt_mod.ingest_youtube_videos())

    conn = db_module.get_connection()
    row = conn.execute("SELECT title FROM feed_cards WHERE id = 'yt:entity-vid-1'").fetchone()
    conn.close()
    assert row["title"] == "POP MART & MYSTERY EGGS"


def test_parse_published_at_handles_z_suffix():
    ts = yt_mod._parse_published_at("2026-08-01T12:00:00Z")
    assert ts > 0


def test_parse_published_at_falls_back_to_now_for_invalid_input():
    before = yt_mod._parse_published_at(None)
    assert before > 0
    fallback = yt_mod._parse_published_at("not-a-date")
    assert fallback > 0
