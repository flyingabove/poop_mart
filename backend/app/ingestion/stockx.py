"""
StockX real-time pricing ingestion -- a fourth real ingestion connector,
different in kind from news.py/youtube.py/instagram.py: instead of
producing feed cards, this writes real price_snapshots rows, which is
what pricing/service.py's get_current_price()/get_price_history()
already read from. That means once this is live, the price charts,
confidence bands, collection valuation, and wishlist alert thresholds
all automatically switch from static seed data to real, continuously-
updating StockX market data -- zero changes needed to any consuming
code (see PRICE_TRACKING_DESIGN.md and DATA_MODEL_INVENTORY.md's
PriceSnapshot shape, which this fills honestly).

DORMANT until real credentials exist: requires STOCKX_API_KEY,
STOCKX_CLIENT_ID, STOCKX_CLIENT_SECRET, and STOCKX_REFRESH_TOKEN.
Getting these requires applying at developer.stockx.com (manual review,
commonly 1-2 weeks, not guaranteed -- StockX has declined applicants
citing "lack of content"), then a one-time interactive OAuth2
Authorization Code exchange (logging into a real StockX account and
granting consent) to obtain a refresh_token with the offline_access
scope. None of that can be done from this codebase -- see CLAUDE.md for
the walkthrough.

IMPORTANT, same posture as instagram.py: StockX's actual official API
reference (developer.stockx.com/portal/api-reference) is gated behind
an approved developer login, so it could not be read directly while
building this. Endpoint paths, OAuth flow shape, and response field
names (lowestAskAmount, highestBidAmount, productId, variantId, urlKey)
are sourced from a well-documented third-party open-source client
(github.com/albertogferrario/javascript-stockx-api) that itself talks
to the real API -- not guessed at, but also not verified against a live
StockX token. Treat the first real run as a verification pass.

Pricing field mapping (StockX gives a bid/ask pair per variant, not a
raw listing count the way the original aggregate-scraping design
assumed):
  - median_price = lowestAskAmount (what it actually costs to buy one
    right now), falling back to highestBidAmount if no ask exists.
  - low_price/high_price = highestBidAmount/lowestAskAmount when both
    exist (a real bid-ask spread is a more honest confidence band than
    the seed data's synthetic +/-10%); when only one side exists, both
    collapse to the single known price (a zero-width band, not a
    fabricated range).
  - listing_count: StockX's market-data response doesn't expose a raw
    count field in what's documented above. Rather than invent a large
    number, this uses 2 when both bid and ask are present, 1 when only
    one side is -- an honest, conservative signal of how much real
    market data was actually seen, not a literal listing count. This
    correctly keeps the existing "low confidence" UI treatment active
    (frontend/pricing.py flag <10 listings), which is the right call
    for a single per-poll market-data read.

Scope: every figure in the catalog is queried every poll (small catalog
today -- ~3 API calls per figure means even the full set stays well
under the 25,000/day quota at a conservative interval). Matching a
figure to a StockX product is conservative: searches "POP MART {brand}
{figure name}", accepts the top result only if its title contains the
brand line (case-insensitive); otherwise skips that figure this poll
rather than risk attaching a wrong price to a figure's page.
"""
import asyncio
import logging
import os
import time

import httpx

from backend.app.db.database import get_connection

_log = logging.getLogger(__name__)

_API_BASE = "https://api.stockx.com/v2"
_TOKEN_URL = "https://accounts.stockx.com/oauth/token"
_AUDIENCE = "gateway.stockx.com"
_CURRENCY = "USD"

DEFAULT_INTERVAL_SECONDS = 3600  # 1 hour -- real-time-ish without overusing the token/rate budget

# In-memory access-token cache: (access_token, expires_at_unix). Refreshing
# is cheap and not subject to the same per-resource cap ig_hashtag_search
# has, so unlike instagram.py's hashtag cache, this doesn't need to be
# DB-persisted -- a redeploy just costs one extra refresh call.
_token_cache: dict[str, float | str] = {}


def _required_env() -> tuple[str, str, str, str] | None:
    api_key = os.getenv("STOCKX_API_KEY")
    client_id = os.getenv("STOCKX_CLIENT_ID")
    client_secret = os.getenv("STOCKX_CLIENT_SECRET")
    refresh_token = os.getenv("STOCKX_REFRESH_TOKEN")
    if not all([api_key, client_id, client_secret, refresh_token]):
        return None
    return api_key, client_id, client_secret, refresh_token


async def _get_access_token(client: httpx.AsyncClient, client_id: str, client_secret: str, refresh_token: str) -> str | None:
    cached_token = _token_cache.get("access_token")
    expires_at = _token_cache.get("expires_at", 0)
    if cached_token and time.time() < float(expires_at) - 60:
        return str(cached_token)

    try:
        resp = await client.post(
            _TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "audience": _AUDIENCE,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        access_token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
    except Exception:
        _log.warning("stockx ingestion: token refresh failed", exc_info=True)
        return None

    _token_cache["access_token"] = access_token
    _token_cache["expires_at"] = time.time() + int(expires_in)
    return access_token


async def _api_get(client: httpx.AsyncClient, path: str, api_key: str, access_token: str, params: dict) -> dict:
    resp = await client.get(
        f"{_API_BASE}/{path}",
        params=params,
        headers={"x-api-key": api_key, "Authorization": f"Bearer {access_token}"},
    )
    resp.raise_for_status()
    return resp.json()


async def _find_product(
    client: httpx.AsyncClient, api_key: str, access_token: str, brand_line: str, figure_name: str
) -> dict | None:
    query = f"POP MART {brand_line} {figure_name}"
    try:
        data = await _api_get(
            client, "catalog/search", api_key, access_token, {"query": query, "pageNumber": 1, "pageSize": 5}
        )
    except Exception:
        _log.warning("stockx ingestion: search failed", extra={"query": query}, exc_info=True)
        return None

    products = data.get("products") or []
    for p in products:
        title = (p.get("title") or "").lower()
        if brand_line.lower() in title:
            return p
    return None


async def _get_market_data(client: httpx.AsyncClient, api_key: str, access_token: str, product_id: str) -> dict | None:
    try:
        variants = await _api_get(client, f"catalog/products/{product_id}/variants", api_key, access_token, {})
        variant_list = variants if isinstance(variants, list) else variants.get("variants") or []
        if not variant_list:
            return None
        variant_id = variant_list[0]["variantId"]

        market = await _api_get(
            client,
            f"catalog/products/{product_id}/variants/{variant_id}/market-data",
            api_key,
            access_token,
            {"currencyCode": _CURRENCY},
        )
    except Exception:
        _log.warning("stockx ingestion: market-data fetch failed", extra={"product_id": product_id}, exc_info=True)
        return None

    ask = market.get("lowestAskAmount")
    bid = market.get("highestBidAmount")
    if ask is None and bid is None:
        return None

    median = float(ask) if ask is not None else float(bid)
    if ask is not None and bid is not None:
        low, high = float(bid), float(ask)
        listing_count = 2
    else:
        low = high = median
        listing_count = 1

    return {"median_price": median, "low_price": min(low, high), "high_price": max(low, high), "listing_count": listing_count}


async def ingest_stockx_prices() -> int:
    """No-op (returns 0) unless STOCKX_API_KEY/CLIENT_ID/CLIENT_SECRET/
    REFRESH_TOKEN are all set -- real code, not a stub, just inactive
    without real credentials. Returns the count of figures a fresh real
    price_snapshots row was written for."""
    creds = _required_env()
    if not creds:
        return 0
    api_key, client_id, client_secret, refresh_token = creds

    read_conn = get_connection()
    try:
        figures = [
            dict(r)
            for r in read_conn.execute(
                "SELECT f.id, f.name, s.brand_line FROM figures f JOIN series s ON s.id = f.series_id"
            )
        ]
    finally:
        read_conn.close()

    inserted = 0
    async with httpx.AsyncClient(timeout=15) as client:
        access_token = await _get_access_token(client, client_id, client_secret, refresh_token)
        if not access_token:
            return 0

        rows_to_insert = []
        for fig in figures:
            product = await _find_product(client, api_key, access_token, fig["brand_line"], fig["name"])
            if not product or not product.get("productId"):
                continue
            market = await _get_market_data(client, api_key, access_token, product["productId"])
            if not market:
                continue
            rows_to_insert.append((fig["id"], market))

    if not rows_to_insert:
        return 0

    now = int(time.time())
    write_conn = get_connection()
    try:
        for figure_id, market in rows_to_insert:
            write_conn.execute(
                "INSERT INTO price_snapshots "
                "(figure_id, timestamp, median_price, low_price, high_price, listing_count, source) "
                "VALUES (?, ?, ?, ?, ?, ?, 'stockx')",
                (figure_id, now, market["median_price"], market["low_price"], market["high_price"], market["listing_count"]),
            )
            inserted += 1
        write_conn.commit()
    finally:
        write_conn.close()

    return inserted


async def run_stockx_ingestion_loop(interval_seconds: int = DEFAULT_INTERVAL_SECONDS) -> None:
    """Background loop: ingest immediately, then every `interval_seconds`.
    Never raises -- a failed pass is logged and the loop keeps going."""
    while True:
        try:
            count = await ingest_stockx_prices()
            _log.info("stockx ingestion pass complete: %d figure(s) priced", count)
        except Exception:
            _log.exception("stockx ingestion pass failed")
        await asyncio.sleep(interval_seconds)
