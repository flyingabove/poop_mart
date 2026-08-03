"""
Seed data for local dev / first deploy.

There is no live ingestion pipeline yet (see backend/app/ingestion/ and
documentation/model_output_docs/TREND_DETECTION_DESIGN.md) — TikTok/Reddit/etc.
connectors need real API credentials this project doesn't have. This seed data
exists so the feed, pricing, guides, and search endpoints are demoable and the
frontend has something real to render against, on a believable Pop Mart catalog.

Idempotent: only inserts if the `series` table is empty.
"""
import time
from backend.app.db.database import get_connection

_DAY = 86400

_SERIES = [
    ("labubu-forest-party", "Labubu Forest Party", "forest party labubu,labubu forest", "Labubu", "2026-06-01", "CN,US,KR,JP"),
    ("labubu-macaron", "Labubu Macaron", "macaron labubu", "Labubu", "2025-11-15", "CN,US,KR,JP,SG"),
    ("crybaby-crying-again", "Crybaby Crying Again", "", "Crybaby", "2026-03-10", "CN,US"),
    ("skullpanda-city-of-night", "Skullpanda City of Night", "", "Skullpanda", "2026-01-20", "CN,KR"),
    ("molly-space-travel", "Molly Space Travel", "", "Molly", "2025-09-05", "CN,US,JP"),
    ("hirono-let-me-rest", "Hirono Let Me Rest", "", "Hirono", "2026-02-14", "CN,US"),
    ("dimoo-world-travel", "Dimoo World Travel", "", "Dimoo", "2025-12-01", "CN,US,SG"),
]

_FIGURES = [
    # id, series_id, name, colorway, is_secret_chase, published_pull_rate, image_url
    ("lfp-forest-ranger", "labubu-forest-party", "Forest Ranger", "Green/Brown", 0, 1 / 8, None),
    ("lfp-berry-picker", "labubu-forest-party", "Berry Picker", "Pink/Red", 0, 1 / 8, None),
    ("lfp-mushroom-nap", "labubu-forest-party", "Mushroom Nap", "Beige/Red", 0, 1 / 8, None),
    ("lfp-firefly-watcher", "labubu-forest-party", "Firefly Watcher", "Yellow/Black", 0, 1 / 8, None),
    ("lfp-acorn-hoarder", "labubu-forest-party", "Acorn Hoarder", "Brown/Tan", 0, 1 / 8, None),
    ("lfp-pinecone-guard", "labubu-forest-party", "Pinecone Guard", "Dark Green", 0, 1 / 8, None),
    ("lfp-moonlit-wanderer", "labubu-forest-party", "Moonlit Wanderer", "Silver/Glow", 1, 1 / 72, None),
    ("lm-vanilla", "labubu-macaron", "Vanilla", "Cream", 0, 1 / 6, None),
    ("lm-pistachio", "labubu-macaron", "Pistachio", "Green", 0, 1 / 6, None),
    ("cb-tears", "crybaby-crying-again", "Tears Again", "Blue", 0, 1 / 8, None),
    ("sp-nightwatch", "skullpanda-city-of-night", "Nightwatch", "Black/Purple", 0, 1 / 8, None),
]

# figure_id -> (weight_range_g, sound_description, distinguishing_notes)
_SHAKE_SIGNATURES = {
    "lfp-forest-ranger": ("46-48g", "single soft thud, no rattle", "Solid pose, no loose parts."),
    "lfp-berry-picker": ("44-46g", "light rattle near the top", "Basket accessory shifts slightly."),
    "lfp-mushroom-nap": ("50-52g", "muffled, heavy, minimal movement", "Extra mushroom accessory adds weight."),
    "lfp-firefly-watcher": ("45-47g", "faint high-pitched rattle", "Small jar accessory taps the box wall."),
    "lfp-acorn-hoarder": ("47-49g", "soft double-tap rattle", "Two acorn accessories knock together."),
    "lfp-pinecone-guard": ("46-48g", "single soft thud, no rattle", "Similar to Forest Ranger — hardest to tell apart by weight alone."),
    "lfp-moonlit-wanderer": ("52-54g", "heavier, faint metallic-ish clink", "Glow accessory + extra paint mass — the chase figure runs noticeably heavier."),
}

_GUIDE_CONTRIBUTIONS = {
    "lfp-forest-ranger": 3,
    "lfp-berry-picker": 2,
    "lfp-mushroom-nap": 4,
    "lfp-firefly-watcher": 2,
    "lfp-acorn-hoarder": 2,
    "lfp-pinecone-guard": 1,
    "lfp-moonlit-wanderer": 6,
}


def _feed_cards(now: int):
    return [
        ("f-trend-1", "trending", "lfp-forest-ranger", "labubu-forest-party",
         "Labubu Forest Party is up 18% this week",
         "Discussion volume and resale prices both climbed after several unboxing videos suggested the Forest Ranger pose is rarer than the printed odds.",
         "community", '{"videos": 24, "news": 3, "discussions": 9}', 0.71, "Global", now - 1 * 3600),

        ("f-whats-hot-1", "whats_hot", "lfp-moonlit-wanderer", "labubu-forest-party",
         "Labubu Forest Party is exploding in Korea",
         "Seoul resale listings for the secret Moonlit Wanderer have more than doubled in three days.",
         "verified_creator", '{"videos": 18, "news": 2, "discussions": 14}', 0.83, "Korea", now - 5 * 3600),

        ("f-new-drop-1", "new_drop", None, "crybaby-crying-again",
         "Crybaby Crying Again launches worldwide",
         "Pop Mart's new Crybaby series goes live in China and the US today, eight regular figures plus one secret.",
         "official", None, None, "Global", now - 2 * _DAY),

        ("f-video-1", "video", "lfp-berry-picker", "labubu-forest-party",
         "\"How I told Berry Picker apart before opening\" is blowing up",
         "A creator's weight-and-rattle demo for Forest Party has crossed 2M views this week.",
         "verified_creator", None, None, "Global", now - 8 * 3600),

        ("f-community-1", "community_post", "lfp-mushroom-nap", "labubu-forest-party",
         "Full Forest Party set pulled from one case",
         "A collector showcased a complete 6+1 case pull, including the secret Moonlit Wanderer.",
         "community", None, None, "US", now - 12 * 3600),

        ("f-price-1", "price_change", "lfp-moonlit-wanderer", "labubu-forest-party",
         "Moonlit Wanderer resale jumps from $82 to $118",
         "Secondary market prices for the Forest Party secret figure are up 44% in two days as supply tightens.",
         "community", None, None, "Global", now - 3 * 3600),

        ("f-price-2", "price_change", "lm-pistachio", "labubu-macaron",
         "Labubu Macaron Pistachio drifting down",
         "Resale median has slid 9% over the past week as the series settles post-launch.",
         "community", None, None, "Global", now - 1 * _DAY),

        ("f-leak-1", "leak", None, "labubu-forest-party",
         "Rumored Labubu \"Winter Forest\" follow-up series",
         "Collectors are speculating about a winter-themed follow-up based on an unconfirmed factory photo — nothing official yet.",
         "unverified", None, None, "China", now - 6 * 3600),

        ("f-review-1", "review", "sp-nightwatch", "skullpanda-city-of-night",
         "Skullpanda Nightwatch: sentiment 89% positive",
         "Main praise is the paint finish; main complaints are occasional box corner damage in transit.",
         "community", None, 0.89, "Global", now - 4 * _DAY),

        ("f-regional-1", "regional_news", None, "molly-space-travel",
         "Molly Space Travel gets a Japan-exclusive colorway",
         "Pop Mart Japan confirmed a store-exclusive variant not sold in other regions.",
         "official", None, None, "Japan", now - 5 * _DAY),

        ("f-shake-1", "shake_guide", None, "labubu-forest-party",
         "Shake Guide updated for Labubu Forest Party",
         "Weight and rattle signatures for all 7 figures now have enough contributions to be worth trusting — the secret Moonlit Wanderer is the clearest tell in the set.",
         "community", None, None, "Global", now - 30 * 60),

        ("f-trend-2", "trending", "cb-tears", "crybaby-crying-again",
         "Crybaby Tears Again trending on launch day",
         "First-day resale listings are already appearing above retail.",
         "community", '{"videos": 6, "news": 1, "discussions": 3}', 0.6, "Global", now - 45 * 60),
    ]


def seed_if_empty() -> None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT COUNT(*) AS n FROM series").fetchone()
        if row["n"] > 0:
            return

        now = int(time.time())

        conn.executemany(
            "INSERT INTO series (id, name, aliases, brand_line, release_date, regions) VALUES (?, ?, ?, ?, ?, ?)",
            _SERIES,
        )
        conn.executemany(
            "INSERT INTO figures (id, series_id, name, colorway, is_secret_chase, published_pull_rate, image_url) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            _FIGURES,
        )
        conn.executemany(
            "INSERT INTO feed_cards (id, card_type, figure_id, series_id, title, body, source_trust_tier, "
            "source_counts_json, sentiment_score, region, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _feed_cards(now),
        )

        # Price history: a rising figure, a falling figure, a launch-day figure.
        price_series = {
            "lfp-moonlit-wanderer": [70, 74, 82, 95, 105, 118],
            "lm-pistachio": [58, 56, 54, 52, 51, 49],
            "cb-tears": [45, 46, 47, 48],
        }
        price_rows = []
        for figure_id, points in price_series.items():
            for i, median in enumerate(points):
                ts = now - (len(points) - i) * _DAY
                price_rows.append((figure_id, ts, float(median), float(median) * 0.9, float(median) * 1.12, 8 + i * 3, "aggregate"))
        conn.executemany(
            "INSERT INTO price_snapshots (figure_id, timestamp, median_price, low_price, high_price, listing_count, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            price_rows,
        )

        # One fully-populated Shake Guide for Labubu Forest Party.
        conn.execute(
            "INSERT INTO shake_guides (id, series_id, technique_summary, created_at) VALUES (?, ?, ?, ?)",
            (
                "guide-labubu-forest-party",
                "labubu-forest-party",
                "Weight is the most reliable tell in this set — Mushroom Nap and the secret Moonlit Wanderer both "
                "run noticeably heavier than the other five poses. Forest Ranger and Pinecone Guard are nearly "
                "identical by weight and rattle, so they're the hardest pair to call before opening.",
                now - 2 * _DAY,
            ),
        )

        contrib_rows = []
        contrib_id_seed = 0
        for figure_id, (weight_range, sound, _notes) in _SHAKE_SIGNATURES.items():
            n = _GUIDE_CONTRIBUTIONS[figure_id]
            for i in range(n):
                contrib_id_seed += 1
                contrib_rows.append((
                    "guide-labubu-forest-party",
                    figure_id,
                    "weight" if i % 2 == 0 else "sound",
                    f"Measured {weight_range} on a kitchen scale, {sound}." if i % 2 == 0 else f"Rattle test: {sound}.",
                    weight_range,
                    3 + i,
                    0 if i < n - 1 else 1,
                    None,
                    now - (n - i) * 3 * 3600,
                ))
        conn.executemany(
            "INSERT INTO guide_contributions (guide_id, figure_id, technique_type, claim_text, weight_range_g, "
            "upvotes, downvotes, video_url, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            contrib_rows,
        )

        conn.commit()
    finally:
        conn.close()
