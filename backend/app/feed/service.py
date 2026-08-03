"""
Feed assembly. See documentation/model_output_docs/FEED_SYSTEM_DESIGN.md.

v1 ranking (per that doc) is a simple weighted blend, not a learned model:
recency + a trust-tier bump + (when the caller is logged in) a real
personalization_match term against the user's followed series — see
backend/app/follows/service.py. Anonymous requests, or a for_you request
with no follows yet, get the same unpersonalized ranking as Trending.

Community posts (the 📷 card type) were always documented as "people
showing collections and pulls" but were seed-data only until now --
create_community_post() is the real, user-authored path. A post requires
a figure_id (the "pull" being shown); its series_id is looked up
automatically so the card still participates in series-follow
personalization like any other card.
"""
import json
import time
import uuid

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
        "poster": row["poster"],
        "poster_id": row["user_id"],
    }


def list_feed(
    tab: str = "for_you",
    card_type: str | None = None,
    limit: int = 50,
    followed_series: set[str] | None = None,
    followed_users: set[str] | None = None,
    region: str | None = None,
) -> list[dict]:
    conn = get_connection()
    try:
        clauses, params = [], []

        if card_type:
            clauses.append("fc.card_type = ?")
            params.append(card_type)
        elif tab in _TAB_CARD_TYPES:
            placeholders = ",".join("?" for _ in _TAB_CARD_TYPES[tab])
            clauses.append(f"fc.card_type IN ({placeholders})")
            params.extend(_TAB_CARD_TYPES[tab])
        # "for_you" / unrecognized tab: no filter, same as Trending unpersonalized.

        if region:
            # FEED_SYSTEM_DESIGN.md's Tabs table documents Trending as
            # "city/region filterable" -- exact match against the card's
            # own region tag, not a Global-inclusive fallback, so a
            # region filter shows only content specifically about that
            # region rather than diluting it with everything untagged.
            clauses.append("fc.region = ?")
            params.append(region)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"SELECT fc.*, u.email AS poster_email FROM feed_cards fc "
            f"LEFT JOIN users u ON u.id = fc.user_id {where} "
            f"ORDER BY fc.created_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()

        now = int(time.time())
        personalize = tab == "for_you" and bool(followed_series or followed_users)
        cards = []
        for r in rows:
            d = dict(r)
            d["poster"] = d["poster_email"].split("@")[0] if d.get("poster_email") else None
            cards.append(_row_to_card(d))
        for c in cards:
            age_hours = max((now - c["created_at"]) / 3600, 0.01)
            recency_decay = 1 / (1 + age_hours / 24)
            trust = _TRUST_WEIGHT.get(c["source_trust_tier"], 0.4)
            score = 0.6 * recency_decay + 0.25 * trust
            if personalize:
                # personalization_match per FEED_SYSTEM_DESIGN.md covers both
                # followed series AND followed creators -- a card matches if
                # either its series or its poster is followed, not series
                # alone (that gap meant following a creator with no series
                # follows produced a fully unpersonalized feed).
                series_match = bool(followed_series) and c["series_id"] in followed_series
                creator_match = bool(followed_users) and c["poster_id"] in followed_users
                match = 1.0 if (series_match or creator_match) else 0.0
                score += 0.15 * match
                c["followed"] = bool(match)
            c["_score"] = round(score, 4)
        cards.sort(key=lambda c: c["_score"], reverse=True)
        return cards
    finally:
        conn.close()


def list_posts_by_user(user_id: str, limit: int = 50) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT fc.id, fc.figure_id, fc.series_id, fc.title, fc.body, fc.created_at, f.name AS figure_name "
            "FROM feed_cards fc JOIN figures f ON f.id = fc.figure_id "
            "WHERE fc.card_type = 'community_post' AND fc.user_id = ? "
            "ORDER BY fc.created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


class FeedError(Exception):
    pass


def create_community_post(user_id: str, figure_id: str, title: str, body: str) -> dict:
    title = title.strip()
    body = body.strip()
    if not title:
        raise FeedError("title is required")
    if not body:
        raise FeedError("body is required")

    conn = get_connection()
    try:
        figure = conn.execute("SELECT series_id FROM figures WHERE id = ?", (figure_id,)).fetchone()
        if not figure:
            raise FeedError("figure not found")

        card_id = f"post:{uuid.uuid4()}"
        now = int(time.time())
        conn.execute(
            "INSERT INTO feed_cards "
            "(id, card_type, figure_id, series_id, title, body, source_trust_tier, region, user_id, created_at) "
            "VALUES (?, 'community_post', ?, ?, ?, ?, 'community', 'Global', ?, ?)",
            (card_id, figure_id, figure["series_id"], title, body, user_id, now),
        )
        conn.commit()
        return {"id": card_id, "figure_id": figure_id, "series_id": figure["series_id"], "created_at": now}
    finally:
        conn.close()


def remove_post(user_id: str, post_id: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM feed_cards WHERE id = ? AND card_type = 'community_post' AND user_id = ?",
            (post_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
