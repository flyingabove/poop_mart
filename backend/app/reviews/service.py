"""Per-figure reviews. See documentation/model_output_docs/USER_PROFILES_AND_SOCIAL_DESIGN.md
(reviews) and DATA_MODEL_INVENTORY.md (Review entity).

One review per user per figure -- posting again updates it (upsert) rather
than stacking duplicate reviews. Reviewer identity shown publicly is the
email's local part (before @), not the full address -- there's no separate
display-name/username field yet, and showing a full email on a public
review is more than this feature needs to expose.

Helpfulness voting: USER_PROFILES_AND_SOCIAL_DESIGN.md defines "Top
Reviewer" as review volume *and* helpfulness votes, but only volume was
ever implemented (badges/service.py). Unlike guide_contributions, the
`reviews` table has no seed data and never had hardcoded vote counts, so
helpful/unhelpful counts here are computed purely from `review_votes` --
no baseline-offset merging needed, unlike the guide-contribution case.

Feed cards: FEED_SYSTEM_DESIGN.md lists "⭐ Reviews" as a first-class feed
card type alongside "📷 Community Posts" -- the frontend has always had a
CARD_ICON/CARD_LABEL entry for it and the seed data ships one example
(f-review-1), but until now nothing ever created one for a *real* review,
same gap Community Posts had before it was closed. Posting/updating a
review now upserts a matching feed card (id `review:<user_id>:<figure_id>`,
so editing a review updates its card in place rather than stacking
duplicates -- same one-per-user-per-figure invariant the reviews table
itself enforces), and removing a review removes its card.
"""
import time

from backend.app.db.database import get_connection


class ReviewError(Exception):
    pass


def _display_handle(email: str) -> str:
    return email.split("@")[0]


def _review_card_id(user_id: str, figure_id: str) -> str:
    return f"review:{user_id}:{figure_id}"


def add_or_update_review(user_id: str, figure_id: str, rating: int, text: str | None) -> dict:
    if rating not in (1, 2, 3, 4, 5):
        raise ReviewError("rating must be an integer from 1 to 5")

    conn = get_connection()
    try:
        figure = conn.execute("SELECT name, series_id FROM figures WHERE id = ?", (figure_id,)).fetchone()
        if not figure:
            raise ReviewError("figure not found")
        now = int(time.time())
        conn.execute(
            "INSERT INTO reviews (user_id, figure_id, rating, text, created_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id, figure_id) DO UPDATE SET "
            "rating = excluded.rating, text = excluded.text, created_at = excluded.created_at",
            (user_id, figure_id, rating, text, now),
        )

        card_id = _review_card_id(user_id, figure_id)
        title = f"Rated {figure['name']} {rating}/5"
        body = text or "No written review."
        conn.execute(
            "INSERT INTO feed_cards "
            "(id, card_type, figure_id, series_id, title, body, source_trust_tier, region, user_id, created_at) "
            "VALUES (?, 'review', ?, ?, ?, ?, 'community', 'Global', ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "title = excluded.title, body = excluded.body, created_at = excluded.created_at",
            (card_id, figure_id, figure["series_id"], title, body, user_id, now),
        )
        conn.commit()
        return {"figure_id": figure_id, "rating": rating, "text": text}
    finally:
        conn.close()


def remove_review(user_id: str, figure_id: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM reviews WHERE user_id = ? AND figure_id = ?", (user_id, figure_id))
        conn.execute("DELETE FROM feed_cards WHERE id = ?", (_review_card_id(user_id, figure_id),))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_reviews(figure_id: str, limit: int = 50, user_id: str | None = None) -> dict:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT r.id, r.rating, r.text, r.created_at, u.email "
            "FROM reviews r JOIN users u ON u.id = r.user_id "
            "WHERE r.figure_id = ? ORDER BY r.created_at DESC LIMIT ?",
            (figure_id, limit),
        ).fetchall()

        vote_rows = conn.execute(
            "SELECT review_id, "
            "SUM(CASE WHEN direction = 'helpful' THEN 1 ELSE 0 END) AS helpful, "
            "SUM(CASE WHEN direction = 'unhelpful' THEN 1 ELSE 0 END) AS unhelpful "
            "FROM review_votes "
            "WHERE review_id IN (SELECT id FROM reviews WHERE figure_id = ?) "
            "GROUP BY review_id",
            (figure_id,),
        ).fetchall()
        vote_counts = {r["review_id"]: (r["helpful"] or 0, r["unhelpful"] or 0) for r in vote_rows}

        my_votes: dict[int, str] = {}
        if user_id:
            my_vote_rows = conn.execute(
                "SELECT review_id, direction FROM review_votes "
                "WHERE user_id = ? AND review_id IN (SELECT id FROM reviews WHERE figure_id = ?)",
                (user_id, figure_id),
            ).fetchall()
            my_votes = {r["review_id"]: r["direction"] for r in my_vote_rows}

        reviews = []
        for row in rows:
            helpful, unhelpful = vote_counts.get(row["id"], (0, 0))
            reviews.append({
                "id": row["id"],
                "rating": row["rating"],
                "text": row["text"],
                "created_at": row["created_at"],
                "reviewer": _display_handle(row["email"]),
                "helpful_count": helpful,
                "unhelpful_count": unhelpful,
                "my_vote": my_votes.get(row["id"]),
            })

        agg = conn.execute(
            "SELECT AVG(rating) AS avg_rating, COUNT(*) AS n FROM reviews WHERE figure_id = ?", (figure_id,)
        ).fetchone()
        return {
            "average_rating": round(agg["avg_rating"], 2) if agg["avg_rating"] is not None else None,
            "review_count": agg["n"],
            "reviews": reviews,
        }
    finally:
        conn.close()


_ALLOWED_REVIEW_VOTE_DIRECTIONS = {"helpful", "unhelpful"}


def vote_review(user_id: str, review_id: int, direction: str) -> dict:
    if direction not in _ALLOWED_REVIEW_VOTE_DIRECTIONS:
        raise ValueError(f"direction must be one of {sorted(_ALLOWED_REVIEW_VOTE_DIRECTIONS)}")

    conn = get_connection()
    try:
        if not conn.execute("SELECT id FROM reviews WHERE id = ?", (review_id,)).fetchone():
            raise ValueError("review not found")

        now = int(time.time())
        conn.execute(
            "INSERT INTO review_votes (user_id, review_id, direction, created_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id, review_id) DO UPDATE SET "
            "direction = excluded.direction, created_at = excluded.created_at",
            (user_id, review_id, direction, now),
        )
        conn.commit()

        row = conn.execute(
            "SELECT "
            "SUM(CASE WHEN direction = 'helpful' THEN 1 ELSE 0 END) AS helpful, "
            "SUM(CASE WHEN direction = 'unhelpful' THEN 1 ELSE 0 END) AS unhelpful "
            "FROM review_votes WHERE review_id = ?",
            (review_id,),
        ).fetchone()
        return {
            "review_id": review_id,
            "my_vote": direction,
            "helpful_count": row["helpful"] or 0,
            "unhelpful_count": row["unhelpful"] or 0,
        }
    finally:
        conn.close()


def list_reviews_by_user(user_id: str, limit: int = 50) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT r.id, r.figure_id, r.rating, r.text, r.created_at, f.name AS figure_name "
            "FROM reviews r JOIN figures f ON f.id = r.figure_id "
            "WHERE r.user_id = ? ORDER BY r.created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_user_review(user_id: str, figure_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT rating, text FROM reviews WHERE user_id = ? AND figure_id = ?", (user_id, figure_id)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
