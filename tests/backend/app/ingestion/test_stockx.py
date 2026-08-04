import asyncio

import pytest

from backend.app.db import database as db_module
from backend.app.ingestion import stockx as sx_mod


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class _FakeStockxClient:
    token_post_calls = 0
    market_data_by_product: dict = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, data=None):
        assert url == sx_mod._TOKEN_URL
        assert data["grant_type"] == "refresh_token"
        _FakeStockxClient.token_post_calls += 1
        return _FakeResponse({"access_token": "fake-access-token", "expires_in": 3600})

    async def get(self, url, params=None, headers=None):
        assert headers["x-api-key"] == "test-api-key"
        assert headers["Authorization"] == "Bearer fake-access-token"

        if url.endswith("/catalog/search"):
            query = params["query"]
            # figure_name is always the last word(s) of our test queries;
            # encode which product this search should resolve to via the
            # query text itself so different figures map to different
            # productIds.
            product_id = f"prod-{abs(hash(query))}"
            return _FakeResponse({"products": [{"productId": product_id, "title": query}]})
        if url.endswith("/variants"):
            product_id = url.rsplit("/", 2)[-2]
            return _FakeResponse({"variants": [{"variantId": f"var-{product_id}"}]})
        if url.endswith("/market-data"):
            product_id = url.rsplit("/", 3)[-3]
            market = _FakeStockxClient.market_data_by_product.get(product_id, {"lowestAskAmount": "50", "highestBidAmount": "40"})
            return _FakeResponse(market)
        raise AssertionError(f"unexpected url {url}")


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    db_module.init_db()
    conn = db_module.get_connection()
    conn.execute(
        "INSERT INTO series (id, name, aliases, brand_line, release_date, regions) VALUES (?, ?, ?, ?, ?, ?)",
        ("test-series", "Test Series", "", "Labubu", "2026-01-01", "Global"),
    )
    conn.execute(
        "INSERT INTO figures (id, series_id, name, colorway, is_secret_chase, published_pull_rate, image_url) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("test-figure-1", "test-series", "Forest Ranger", "Green", 0, 0.125, None),
    )
    conn.commit()
    conn.close()

    _FakeStockxClient.token_post_calls = 0
    _FakeStockxClient.market_data_by_product = {}
    sx_mod._token_cache.clear()
    yield


def _set_creds(monkeypatch):
    monkeypatch.setenv("STOCKX_API_KEY", "test-api-key")
    monkeypatch.setenv("STOCKX_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("STOCKX_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("STOCKX_REFRESH_TOKEN", "test-refresh-token")


def test_ingest_noop_without_credentials(isolated_db, monkeypatch):
    monkeypatch.delenv("STOCKX_API_KEY", raising=False)
    monkeypatch.delenv("STOCKX_CLIENT_ID", raising=False)
    monkeypatch.delenv("STOCKX_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("STOCKX_REFRESH_TOKEN", raising=False)
    monkeypatch.setattr(sx_mod.httpx, "AsyncClient", _FakeStockxClient)

    count = asyncio.run(sx_mod.ingest_stockx_prices())
    assert count == 0

    conn = db_module.get_connection()
    rows = conn.execute("SELECT * FROM price_snapshots WHERE source = 'stockx'").fetchall()
    conn.close()
    assert rows == []


def test_ingest_noop_with_partial_credentials(isolated_db, monkeypatch):
    monkeypatch.setenv("STOCKX_API_KEY", "test-api-key")
    monkeypatch.setenv("STOCKX_CLIENT_ID", "test-client-id")
    monkeypatch.delenv("STOCKX_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("STOCKX_REFRESH_TOKEN", raising=False)
    monkeypatch.setattr(sx_mod.httpx, "AsyncClient", _FakeStockxClient)

    count = asyncio.run(sx_mod.ingest_stockx_prices())
    assert count == 0


def test_ingest_inserts_price_snapshot_for_matched_figure(isolated_db, monkeypatch):
    _set_creds(monkeypatch)
    monkeypatch.setattr(sx_mod.httpx, "AsyncClient", _FakeStockxClient)

    count = asyncio.run(sx_mod.ingest_stockx_prices())
    assert count == 1

    conn = db_module.get_connection()
    row = conn.execute(
        "SELECT * FROM price_snapshots WHERE figure_id = 'test-figure-1' AND source = 'stockx'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["median_price"] == 50.0  # lowestAskAmount from the default fake market data


def test_price_mapping_with_both_bid_and_ask(isolated_db, monkeypatch):
    _set_creds(monkeypatch)
    monkeypatch.setattr(sx_mod.httpx, "AsyncClient", _FakeStockxClient)
    # default fake already returns ask=50, bid=40

    asyncio.run(sx_mod.ingest_stockx_prices())

    conn = db_module.get_connection()
    row = conn.execute("SELECT * FROM price_snapshots WHERE source = 'stockx'").fetchone()
    conn.close()
    assert row["median_price"] == 50.0  # ask
    assert row["low_price"] == 40.0  # bid
    assert row["high_price"] == 50.0  # ask
    assert row["listing_count"] == 2  # both sides seen


def test_price_mapping_with_ask_only_collapses_to_single_price(isolated_db, monkeypatch):
    _set_creds(monkeypatch)

    class _AskOnlyClient(_FakeStockxClient):
        async def get(self, url, params=None, headers=None):
            if url.endswith("/market-data"):
                return _FakeResponse({"lowestAskAmount": "75", "highestBidAmount": None})
            return await super().get(url, params=params, headers=headers)

    monkeypatch.setattr(sx_mod.httpx, "AsyncClient", _AskOnlyClient)

    asyncio.run(sx_mod.ingest_stockx_prices())

    conn = db_module.get_connection()
    row = conn.execute("SELECT * FROM price_snapshots WHERE source = 'stockx'").fetchone()
    conn.close()
    assert row["median_price"] == 75.0
    assert row["low_price"] == 75.0
    assert row["high_price"] == 75.0
    assert row["listing_count"] == 1  # only one side seen -- not a fabricated range


def test_no_bid_or_ask_is_skipped_not_crashed(isolated_db, monkeypatch):
    _set_creds(monkeypatch)

    class _NoMarketDataClient(_FakeStockxClient):
        async def get(self, url, params=None, headers=None):
            if url.endswith("/market-data"):
                return _FakeResponse({"lowestAskAmount": None, "highestBidAmount": None})
            return await super().get(url, params=params, headers=headers)

    monkeypatch.setattr(sx_mod.httpx, "AsyncClient", _NoMarketDataClient)

    count = asyncio.run(sx_mod.ingest_stockx_prices())
    assert count == 0


def test_unmatched_search_result_is_skipped_not_crashed(isolated_db, monkeypatch):
    _set_creds(monkeypatch)

    class _WrongBrandClient(_FakeStockxClient):
        async def get(self, url, params=None, headers=None):
            if url.endswith("/catalog/search"):
                return _FakeResponse({"products": [{"productId": "prod-wrong", "title": "Some Unrelated Sneaker"}]})
            return await super().get(url, params=params, headers=headers)

    monkeypatch.setattr(sx_mod.httpx, "AsyncClient", _WrongBrandClient)

    count = asyncio.run(sx_mod.ingest_stockx_prices())
    assert count == 0


def test_access_token_is_cached_across_ingestion_passes(isolated_db, monkeypatch):
    _set_creds(monkeypatch)
    monkeypatch.setattr(sx_mod.httpx, "AsyncClient", _FakeStockxClient)

    asyncio.run(sx_mod.ingest_stockx_prices())
    assert _FakeStockxClient.token_post_calls == 1

    asyncio.run(sx_mod.ingest_stockx_prices())
    assert _FakeStockxClient.token_post_calls == 1, "a still-valid cached token should not be re-fetched"


def test_repeated_ingestion_builds_real_price_history(isolated_db, monkeypatch):
    _set_creds(monkeypatch)
    monkeypatch.setattr(sx_mod.httpx, "AsyncClient", _FakeStockxClient)

    asyncio.run(sx_mod.ingest_stockx_prices())
    asyncio.run(sx_mod.ingest_stockx_prices())

    conn = db_module.get_connection()
    rows = conn.execute(
        "SELECT * FROM price_snapshots WHERE figure_id = 'test-figure-1' AND source = 'stockx'"
    ).fetchall()
    conn.close()
    # Unlike the other connectors' dedup-by-external-id, price_snapshots is
    # a real time series -- each poll should append, not overwrite.
    assert len(rows) == 2
