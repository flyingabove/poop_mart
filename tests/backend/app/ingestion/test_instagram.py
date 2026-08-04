import asyncio

import pytest

from backend.app.db import database as db_module
from backend.app.ingestion import instagram as ig_mod

_BUSINESS_ID = "biz-123"

_OFFICIAL_RESPONSE = {
    "business_discovery": {
        "media": {
            "data": [
                {
                    "id": "official-media-1",
                    "caption": "Official Pop Mart Labubu unboxing",
                    "media_type": "VIDEO",
                    "timestamp": "2026-08-01T12:00:00+0000",
                },
                {
                    "id": "official-media-image-1",
                    "caption": "Just a photo, not a video",
                    "media_type": "IMAGE",
                    "timestamp": "2026-08-01T12:00:00+0000",
                },
            ]
        }
    }
}


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class _FakeInstagramClient:
    hashtag_search_calls: list[str] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, params=None, headers=None):
        if url.endswith("/recent_media"):
            hashtag_id = url.rsplit("/", 2)[-2]
            return _FakeResponse({
                "data": [{
                    "id": f"search-{hashtag_id}",
                    # Deliberately generic -- must not accidentally contain
                    # any known figure/series name as a substring, since
                    # some fixture hashtag names (e.g. "popmartlabubu")
                    # themselves contain "labubu".
                    "caption": "Fan unboxing video, mystery blind box #popmart",
                    "media_type": "VIDEO",
                    "timestamp": "2026-08-01T12:00:00+0000",
                }]
            })
        if url.endswith("/ig_hashtag_search"):
            hashtag = params["q"]
            _FakeInstagramClient.hashtag_search_calls.append(hashtag)
            return _FakeResponse({"data": [{"id": f"hashtagid-{hashtag}"}]})
        # anything else is treated as the business-discovery call
        return _FakeResponse(_OFFICIAL_RESPONSE)


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    db_module.init_db()
    _FakeInstagramClient.hashtag_search_calls = []
    yield


def _set_creds(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", _BUSINESS_ID)


def test_ingest_noop_without_credentials(isolated_db, monkeypatch):
    monkeypatch.delenv("INSTAGRAM_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", raising=False)
    monkeypatch.setattr(ig_mod.httpx, "AsyncClient", _FakeInstagramClient)

    count = asyncio.run(ig_mod.ingest_instagram_videos())
    assert count == 0

    conn = db_module.get_connection()
    rows = conn.execute("SELECT * FROM feed_cards WHERE card_type = 'video'").fetchall()
    conn.close()
    assert rows == []


def test_ingest_noop_with_only_one_of_two_required_vars(isolated_db, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "test-token")
    monkeypatch.delenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", raising=False)
    monkeypatch.setattr(ig_mod.httpx, "AsyncClient", _FakeInstagramClient)

    count = asyncio.run(ig_mod.ingest_instagram_videos())
    assert count == 0


def test_ingest_inserts_official_and_hashtag_videos_and_dedupes(isolated_db, monkeypatch):
    _set_creds(monkeypatch)
    monkeypatch.setattr(ig_mod.httpx, "AsyncClient", _FakeInstagramClient)

    first = asyncio.run(ig_mod.ingest_instagram_videos())
    assert first == 1 + len(ig_mod._HASHTAGS)  # 1 official video (IMAGE skipped) + 1 per hashtag

    second = asyncio.run(ig_mod.ingest_instagram_videos())
    assert second == 0  # same media ids on re-poll -> nothing new


def test_non_video_media_is_skipped(isolated_db, monkeypatch):
    _set_creds(monkeypatch)
    monkeypatch.setattr(ig_mod.httpx, "AsyncClient", _FakeInstagramClient)

    asyncio.run(ig_mod.ingest_instagram_videos())

    conn = db_module.get_connection()
    row = conn.execute("SELECT * FROM feed_cards WHERE id = 'ig:official-media-image-1'").fetchone()
    conn.close()
    assert row is None


def test_official_video_is_tagged_official_tier(isolated_db, monkeypatch):
    _set_creds(monkeypatch)
    monkeypatch.setattr(ig_mod.httpx, "AsyncClient", _FakeInstagramClient)

    asyncio.run(ig_mod.ingest_instagram_videos())

    conn = db_module.get_connection()
    row = conn.execute("SELECT * FROM feed_cards WHERE id = 'ig:official-media-1'").fetchone()
    conn.close()
    assert row is not None
    assert row["source_trust_tier"] == "official"
    assert row["card_type"] == "video"


def test_hashtag_video_is_tagged_community_tier(isolated_db, monkeypatch):
    _set_creds(monkeypatch)
    monkeypatch.setattr(ig_mod.httpx, "AsyncClient", _FakeInstagramClient)

    asyncio.run(ig_mod.ingest_instagram_videos())

    conn = db_module.get_connection()
    rows = conn.execute(
        "SELECT * FROM feed_cards WHERE card_type = 'video' AND source_trust_tier = 'community'"
    ).fetchall()
    conn.close()
    assert len(rows) == len(ig_mod._HASHTAGS)


def test_hashtag_id_is_cached_and_not_reresolved(isolated_db, monkeypatch):
    # ig_hashtag_search is capped at 30 unique hashtags per rolling 7 days
    # -- a second ingestion pass must reuse the cached hashtag_id rather
    # than burning the quota re-resolving the same hashtags every poll.
    _set_creds(monkeypatch)
    monkeypatch.setattr(ig_mod.httpx, "AsyncClient", _FakeInstagramClient)

    asyncio.run(ig_mod.ingest_instagram_videos())
    first_calls = list(_FakeInstagramClient.hashtag_search_calls)
    assert sorted(first_calls) == sorted(ig_mod._HASHTAGS)

    _FakeInstagramClient.hashtag_search_calls = []
    asyncio.run(ig_mod.ingest_instagram_videos())
    assert _FakeInstagramClient.hashtag_search_calls == [], "cached hashtag ids should skip ig_hashtag_search entirely"

    conn = db_module.get_connection()
    cached = conn.execute("SELECT hashtag FROM instagram_hashtag_cache").fetchall()
    conn.close()
    assert {r["hashtag"] for r in cached} == set(ig_mod._HASHTAGS)


def test_ingest_notifies_followers_of_resolved_series(isolated_db, monkeypatch):
    _set_creds(monkeypatch)
    monkeypatch.setattr(ig_mod.httpx, "AsyncClient", _FakeInstagramClient)

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

    asyncio.run(ig_mod.ingest_instagram_videos())

    conn = db_module.get_connection()
    notifs = conn.execute("SELECT * FROM notifications WHERE user_id = ?", ("user-1",)).fetchall()
    conn.close()

    # Only the official video's caption ("...Labubu unboxing") contains
    # "labubu" -- the hashtag-search fake captions don't mention it.
    assert len(notifs) == 1
    assert notifs[0]["series_id"] == "labubu-forest-party"
