"""
In-app notification feed. See documentation/model_output_docs/NOTIFICATIONS_DESIGN.md.

No push infra (APNs/FCM credentials) is available, so v1 is in-app only:
notifications are rows a client polls via GET /api/notifications, not real
push. The one real trigger wired up so far is ingestion -> follows: when
backend/app/ingestion/news.py inserts a genuinely new feed card (not a
re-poll dedup), notify_followers_of_new_card() fires for anyone following
that card's series. Wishlist price-drop alerts (the other documented
trigger) aren't wired yet -- prices are static seed data with no live
feed, so there's no real "price just dropped" event to hook today; revisit
once PRICE_TRACKING_DESIGN.md's real sourcing exists.
"""
import time

from backend.app.db.database import get_connection


def notify_followers_of_new_card(card_id: str, series_id: str | None, title: str) -> int:
    """Called right after a new feed card is inserted. Creates one
    notification per user following the card's series. No-op if the card
    has no series_id or nobody follows it. Returns notifications created."""
    if not series_id:
        return 0

    conn = get_connection()
    try:
        follower_ids = [
            r["user_id"]
            for r in conn.execute(
                "SELECT user_id FROM series_follows WHERE series_id = ?", (series_id,)
            ).fetchall()
        ]
        if not follower_ids:
            return 0

        now = int(time.time())
        conn.executemany(
            "INSERT INTO notifications "
            "(user_id, notification_type, title, body, series_id, feed_card_id, created_at) "
            "VALUES (?, 'followed_series_update', 'New update for a series you follow', ?, ?, ?, ?)",
            [(uid, title, series_id, card_id, now) for uid in follower_ids],
        )
        conn.commit()
        return len(follower_ids)
    finally:
        conn.close()


def list_notifications(user_id: str, unread_only: bool = False, limit: int = 50) -> list[dict]:
    conn = get_connection()
    try:
        where = "WHERE user_id = ?" + (" AND read_at IS NULL" if unread_only else "")
        rows = conn.execute(
            f"SELECT * FROM notifications {where} ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_read(user_id: str, notification_id: int) -> bool:
    conn = get_connection()
    try:
        now = int(time.time())
        cur = conn.execute(
            "UPDATE notifications SET read_at = ? WHERE id = ? AND user_id = ? AND read_at IS NULL",
            (now, notification_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def unread_count(user_id: str) -> int:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM notifications WHERE user_id = ? AND read_at IS NULL", (user_id,)
        ).fetchone()
        return row["n"]
    finally:
        conn.close()
