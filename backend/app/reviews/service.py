"""Per-figure reviews. See documentation/model_output_docs/USER_PROFILES_AND_SOCIAL_DESIGN.md
(reviews) and DATA_MODEL_INVENTORY.md (Review entity).

One review per user per figure -- posting again updates it (upsert) rather
than stacking duplicate reviews. Reviewer identity shown publicly is the
email's local part (before @), not the full address -- there's no separate
display-name/username field yet, and showing a full email on a public
review is more than this feature needs to expose.
"""
import time

from backend.app.db.database import get_connection


class ReviewError(Exception):
    pass


def _display_handle(email: str) -> str:
    return email.split("@")[0]


def add_or_update_review(user_id: str, figure_id: str, rating: int, text: str | None) -> dict:
    if rating not in (1, 2, 3, 4, 5):
        raise ReviewError("rating must be an integer from 1 to 5")

    conn = get_connection()
    try:
        if not conn.execute("SELECT id FROM figures WHERE id = ?", (figure_id,)).fetchone():
            raise ReviewError("figure not found")
        now = int(time.time())
        conn.execute(
            "INSERT INTO reviews (user_id, figure_id, rating, text, created_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id, figure_id) DO UPDATE SET "
            "rating = excluded.rating, text = excluded.text, created_at = excluded.created_at",
            (user_id, figure_id, rating, text, now),
        )
        conn.commit()
        return {"figure_id": figure_id, "rating": rating, "text": text}
    finally:
        conn.close()


def remove_review(user_id: str, figure_id: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM reviews WHERE user_id = ? AND figure_id = ?", (user_id, figure_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_reviews(figure_id: str, limit: int = 50) -> dict:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT r.id, r.rating, r.text, r.created_at, u.email "
            "FROM reviews r JOIN users u ON u.id = r.user_id "
            "WHERE r.figure_id = ? ORDER BY r.created_at DESC LIMIT ?",
            (figure_id, limit),
        ).fetchall()
        reviews = [
            {
                "id": row["id"],
                "rating": row["rating"],
                "text": row["text"],
                "created_at": row["created_at"],
                "reviewer": _display_handle(row["email"]),
            }
            for row in rows
        ]
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


def get_user_review(user_id: str, figure_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT rating, text FROM reviews WHERE user_id = ? AND figure_id = ?", (user_id, figure_id)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
