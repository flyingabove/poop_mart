"""
In-app notification feed. See documentation/model_output_docs/NOTIFICATIONS_DESIGN.md.

No push infra (APNs/FCM credentials) is available, so v1 is in-app only:
notifications are rows a client polls via GET /api/notifications, not real
push. Two real triggers are wired up: (1) ingestion -> series follows --
when backend/app/ingestion/news.py inserts a genuinely new feed card (not
a re-poll dedup), notify_followers_of_new_card() fires for anyone
following that card's series; (2) community posts -> user follows --
notify_followers_of_user_post() fires when a user with followers posts a
pull, satisfying the "social" category NOTIFICATIONS_DESIGN.md's Delivery
Rules already names but never had an implementation for. Wishlist
price-drop alerts (the other documented trigger) aren't wired yet --
prices are static seed data with no live feed, so there's no real "price
just dropped" event to hook today; revisit once PRICE_TRACKING_DESIGN.md's
real sourcing exists.

Preferences: the Delivery Rules also say "all notifications are opt-in
per category ... no bundled all-or-nothing toggle" -- until now there was
no toggle of any kind, bundled or otherwise. notification_preferences
gives per-category control for the categories that are actually real
today (followed_series_update, followed_user_post, shake_guide_update);
price_alerts/restocks aren't wired triggers yet so there's nothing to
toggle for them. Interpreted "opt-in" here as "independently
controllable," not "off until explicitly enabled" -- flipping the
existing, already-shipped notification flow to default-off would be a
silent behavior change for every current user, not a neutral reading of
the doc. A missing preference row means enabled (matches current
behavior); an explicit disabled row overrides that.

shake_guide_update was split out from followed_series_update: the
Delivery Rules list "drops" and "guide updates" as separate opt-in
categories, but both a followed series' regular news/trend cards
(news.py) and its Shake Guide threshold-crossing card
(guides/service.py) called the same notify_followers_of_new_card()
with a hardcoded 'followed_series_update' type -- a collector who
wants Shake Guide contribution alerts but not general series news (or
the reverse) had no way to express that; toggling the one preference
silenced both.
"""
import time

from backend.app.db.database import get_connection

_KNOWN_CATEGORIES = {"followed_series_update", "followed_user_post", "shake_guide_update"}

_GENERIC_TITLE_BY_CATEGORY = {
    "followed_series_update": "New update for a series you follow",
    "shake_guide_update": "Shake Guide update for a series you follow",
}


def get_preferences(user_id: str) -> dict[str, bool]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT category, enabled FROM notification_preferences WHERE user_id = ?", (user_id,)
        ).fetchall()
        overrides = {r["category"]: bool(r["enabled"]) for r in rows}
        return {cat: overrides.get(cat, True) for cat in _KNOWN_CATEGORIES}
    finally:
        conn.close()


def set_preference(user_id: str, category: str, enabled: bool) -> dict:
    if category not in _KNOWN_CATEGORIES:
        raise ValueError(f"category must be one of {sorted(_KNOWN_CATEGORIES)}")
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO notification_preferences (user_id, category, enabled) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, category) DO UPDATE SET enabled = excluded.enabled",
            (user_id, category, int(enabled)),
        )
        conn.commit()
        return {"category": category, "enabled": enabled}
    finally:
        conn.close()


def _is_enabled(conn, user_id: str, category: str) -> bool:
    row = conn.execute(
        "SELECT enabled FROM notification_preferences WHERE user_id = ? AND category = ?",
        (user_id, category),
    ).fetchone()
    return bool(row["enabled"]) if row else True


def notify_followers_of_new_card(
    card_id: str, series_id: str | None, title: str, category: str = "followed_series_update"
) -> int:
    """Called right after a new feed card is inserted. Creates one
    notification per user following the card's series (skipping anyone who
    has opted out of this category). No-op if the card has no series_id or
    nobody follows it. Returns notifications created.

    `category` lets callers route into a distinct opt-in preference --
    e.g. Shake Guide threshold-crossing cards use 'shake_guide_update' so
    they're independently controllable from general series news/trend
    cards, per NOTIFICATIONS_DESIGN.md listing "drops" and "guide
    updates" as separate categories."""
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
        follower_ids = [uid for uid in follower_ids if _is_enabled(conn, uid, category)]
        if not follower_ids:
            return 0

        now = int(time.time())
        generic_title = _GENERIC_TITLE_BY_CATEGORY.get(
            category, _GENERIC_TITLE_BY_CATEGORY["followed_series_update"]
        )
        conn.executemany(
            "INSERT INTO notifications "
            "(user_id, notification_type, title, body, series_id, feed_card_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(uid, category, generic_title, title, series_id, card_id, now) for uid in follower_ids],
        )
        conn.commit()
        return len(follower_ids)
    finally:
        conn.close()


def notify_followers_of_user_post(poster_id: str, post_id: str, figure_id: str, series_id: str | None, post_title: str) -> int:
    """Called right after a community post is created. Creates one
    notification per user following the poster (skipping anyone who has
    opted out of this category). No-op if nobody follows them. Returns
    notifications created."""
    conn = get_connection()
    try:
        poster = conn.execute("SELECT email FROM users WHERE id = ?", (poster_id,)).fetchone()
        if not poster:
            return 0
        handle = poster["email"].split("@")[0]

        follower_ids = [
            r["follower_id"]
            for r in conn.execute(
                "SELECT follower_id FROM user_follows WHERE followed_id = ?", (poster_id,)
            ).fetchall()
        ]
        follower_ids = [uid for uid in follower_ids if _is_enabled(conn, uid, "followed_user_post")]
        if not follower_ids:
            return 0

        now = int(time.time())
        conn.executemany(
            "INSERT INTO notifications "
            "(user_id, notification_type, title, body, figure_id, series_id, feed_card_id, created_at) "
            "VALUES (?, 'followed_user_post', ?, ?, ?, ?, ?, ?)",
            [
                (uid, f"@{handle} shared a new pull", post_title, figure_id, series_id, post_id, now)
                for uid in follower_ids
            ],
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
