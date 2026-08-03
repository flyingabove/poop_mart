"""
Feed assembly. See documentation/model_output_docs/FEED_SYSTEM_DESIGN.md.

v1 ranking (per that doc) is a simple weighted blend, not a learned model:
recency + a trust-tier bump + (when the caller is logged in) a real
personalization_match term against the user's followed series — see
backend/app/follows/service.py. Anonymous requests, or a for_you request
with no follows yet, get the same unpersonalized ranking as Trending.
"""
import json
import time
from backend.app.db.database import get_connection

_TRUST_WEIGHT = {
    "official": 1.0,
    "verified_creator": 0.7,
    "community": 0.4,
    "unverified": 0.1,
}

_TAB_CARD_TYPES = {
    "trending": {"trending", "whats_hot", "price_change"},
    "news": {"new_drop", "regional_news"},
    "videos": {"video"},
    "collections": {"community_post"},
    "guides": {"shake_guide"},
    "marketplace": {"price_change", "trending"},
}


def _row_to_card(row) -> dict:
    return {
        "id": row["id"],
        "card_type": row["card_type"],
        "figure_id": row["figure_id"],
        "series_id": row["series_id"],
        "title": row["title"],
        "body": row["body"],
        "source_trust_tier": row["source_trust_tier"],
        "source_counts": json.loads(row["source_counts_json"]) if row["source_counts_json"] else None,
        "sentiment_score": row["sentiment_score"],
        "region": row["region"],
        "created_at": row["created_at"],
    }


def list_feed(
    tab: str = "for_you",
    card_type: str | None = None,
    limit: int = 50,
    followed_series: set[str] | None = None,
) -> list[dict]:
    conn = get_connection()
    try:
        clauses, params = [], []

        if card_type:
            clauses.append("card_type = ?")
            params.append(card_type)
        elif tab in _TAB_CARD_TYPES:
            placeholders = ",".join("?" for _ in _TAB_CARD_TYPES[tab])
            clauses.append(f"card_type IN ({placeholders})")
            params.extend(_TAB_CARD_TYPES[tab])
        # "for_you" / unrecognized tab: no filter, same as Trending unpersonalized.

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"SELECT * FROM feed_cards {where} ORDER BY created_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()

        now = int(time.time())
        personalize = tab == "for_you" and followed_series
        cards = [_row_to_card(r) for r in rows]
        for c in cards:
            age_hours = max((now - c["created_at"]) / 3600, 0.01)
            recency_decay = 1 / (1 + age_hours / 24)
            trust = _TRUST_WEIGHT.get(c["source_trust_tier"], 0.4)
            score = 0.6 * recency_decay + 0.25 * trust
            if personalize:
                match = 1.0 if c["series_id"] in followed_series else 0.0
                score += 0.15 * match
                c["followed"] = bool(match)
            c["_score"] = round(score, 4)
        cards.sort(key=lambda c: c["_score"], reverse=True)
        return cards
    finally:
        conn.close()
