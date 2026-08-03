import asyncio

import pytest

from backend.app.db import database as db_module
from backend.app.ingestion import news as news_mod

_RSS_TEMPLATE = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item>
  <title>{title}</title>
  <link>https://example.com/article-{guid}</link>
  <guid isPermaLink="false">{guid}</guid>
  <pubDate>Mon, 03 Aug 2026 12:00:00 GMT</pubDate>
  <source url="https://example.com">Example Times</source>
</item>
</channel></rss>
"""


class _FakeResponse:
    def __init__(self, text):
        self._text = text

    def raise_for_status(self):
        pass

    @property
    def text(self):
        return self._text


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, params=None, headers=None):
        query = params["q"]
        title = f"Big news about {query}"
        guid = f"guid-{abs(hash(query))}"
        return _FakeResponse(_RSS_TEMPLATE.format(title=title, guid=guid))


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    db_module.init_db()
    yield


def test_ingest_google_news_inserts_and_dedupes(isolated_db, monkeypatch):
    monkeypatch.setattr(news_mod.httpx, "AsyncClient", _FakeAsyncClient)

    first = asyncio.run(news_mod.ingest_google_news())
    assert first == len(news_mod._QUERIES)  # one card per query, all new

    second = asyncio.run(news_mod.ingest_google_news())
    assert second == 0  # same guids on re-poll -> nothing new


def test_ingest_does_not_hold_a_connection_open_across_network_fetches(isolated_db, monkeypatch):
    """Regression test for the "database is locked" bug: a DB connection
    must never be open while a network fetch is in flight. Records the
    interleaving of get_connection() calls vs. network fetches and asserts
    they never overlap -- exactly two connections total (one to read the
    catalog up front, one to write at the end), both outside the fetch
    window, regardless of how many queries are polled."""
    call_order = []

    class _TrackingFakeAsyncClient(_FakeAsyncClient):
        async def get(self, url, params=None, headers=None):
            call_order.append(("fetch", params["q"]))
            return await super().get(url, params=params, headers=headers)

    monkeypatch.setattr(news_mod.httpx, "AsyncClient", _TrackingFakeAsyncClient)

    real_get_connection = news_mod.get_connection

    def _tracking_get_connection():
        call_order.append(("connect",))
        return real_get_connection()

    monkeypatch.setattr(news_mod, "get_connection", _tracking_get_connection)

    asyncio.run(news_mod.ingest_google_news())

    connect_indices = [i for i, c in enumerate(call_order) if c[0] == "connect"]
    fetch_indices = [i for i, c in enumerate(call_order) if c[0] == "fetch"]

    assert len(connect_indices) == 2, "expected exactly one read connection and one write connection"
    assert connect_indices[0] < fetch_indices[0], "the read connection must open (and close) before fetching starts"
    assert connect_indices[1] > fetch_indices[-1], "the write connection must not open until all fetches are done"


def test_ingest_notifies_followers_of_resolved_series(isolated_db, monkeypatch):
    """End-to-end: ingest -> resolve headline to a series -> notify anyone
    following it. The fake client's "Pop Mart Labubu" query produces a
    title containing "labubu", which should resolve via the series alias."""
    monkeypatch.setattr(news_mod.httpx, "AsyncClient", _FakeAsyncClient)

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

    asyncio.run(news_mod.ingest_google_news())

    conn = db_module.get_connection()
    notifs = conn.execute("SELECT * FROM notifications WHERE user_id = ?", ("user-1",)).fetchall()
    conn.close()

    # Exactly one of the 6 tracked queries ("Pop Mart Labubu") should
    # produce a title matching the "labubu" alias -- the rest (Crybaby,
    # Skullpanda, Molly, Dimoo, blind box) shouldn't false-positive.
    assert len(notifs) == 1
    assert notifs[0]["series_id"] == "labubu-forest-party"
    assert "Labubu" in notifs[0]["body"]


def test_parse_items_extracts_fields():
    xml_text = _RSS_TEMPLATE.format(title="Labubu Forest Party restocked", guid="abc123")
    items = news_mod._parse_items(xml_text)
    assert len(items) == 1
    assert items[0]["external_id"] == "gnews:abc123"
    assert items[0]["source_name"] == "Example Times"
    assert items[0]["title"] == "Labubu Forest Party restocked"


def test_resolve_matches_known_figure():
    series = [{"id": "labubu-forest-party", "name": "Labubu Forest Party", "aliases": "forest party labubu"}]
    figures = [{"id": "lfp-forest-ranger", "name": "Forest Ranger", "series_id": "labubu-forest-party"}]

    fig_id, series_id = news_mod._resolve("New Forest Ranger figure spotted in stores", series, figures)
    assert fig_id == "lfp-forest-ranger"
    assert series_id == "labubu-forest-party"


def test_resolve_matches_series_alias_when_no_figure_hit():
    series = [{"id": "labubu-forest-party", "name": "Labubu Forest Party", "aliases": "forest party labubu"}]
    fig_id, series_id = news_mod._resolve("The forest party labubu is everywhere", series, [])
    assert fig_id is None
    assert series_id == "labubu-forest-party"


def test_resolve_returns_none_for_unrelated_headline():
    fig_id, series_id = news_mod._resolve("Completely unrelated headline", [], [])
    assert fig_id is None
    assert series_id is None
