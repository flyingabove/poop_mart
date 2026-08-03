"""Series follows and user (creator) follows.
See documentation/model_output_docs/FEED_SYSTEM_DESIGN.md (personalization_match
in the v1 ranking formula), USER_PROFILES_AND_SOCIAL_DESIGN.md (follows),
and DATA_MODEL_INVENTORY.md (Follow: follower_id, followed_id -- user or
creator).

User-to-user follows were deliberately deferred back when series-follows
were first built: feed_cards had no user_id then (community_post cards
were seed/ingested only), so following a person would have been a button
that did nothing observable. That's no longer true -- community posts are
real and user-authored now, and Rankings expose their owner's id publicly.
Following a user is a real, useful action today.
"""
import time

from backend.app.db.database import get_connection


class FollowError(Exception):
    pass


def follow_series(user_id: str, series_id: str) -> dict:
    conn = get_connection()
    try:
        if not conn.execute("SELECT id FROM series WHERE id = ?", (series_id,)).fetchone():
            raise FollowError("series not found")
        now = int(time.time())
        conn.execute(
            "INSERT OR IGNORE INTO series_follows (user_id, series_id, created_at) VALUES (?, ?, ?)",
            (user_id, series_id, now),
        )
        conn.commit()
        return {"series_id": series_id, "following": True}
    finally:
        conn.close()


def unfollow_series(user_id: str, series_id: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM series_follows WHERE user_id = ? AND series_id = ?", (user_id, series_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_followed_series(user_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT sf.series_id, sf.created_at, s.name, s.brand_line "
            "FROM series_follows sf JOIN series s ON s.id = sf.series_id "
            "WHERE sf.user_id = ? ORDER BY sf.created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def followed_series_ids(user_id: str) -> set[str]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT series_id FROM series_follows WHERE user_id = ?", (user_id,)).fetchall()
        return {r["series_id"] for r in rows}
    finally:
        conn.close()


def follow_user(follower_id: str, followed_id: str) -> dict:
    if follower_id == followed_id:
        raise FollowError("cannot follow yourself")
    conn = get_connection()
    try:
        if not conn.execute("SELECT id FROM users WHERE id = ?", (followed_id,)).fetchone():
            raise FollowError("user not found")
        now = int(time.time())
        conn.execute(
            "INSERT OR IGNORE INTO user_follows (follower_id, followed_id, created_at) VALUES (?, ?, ?)",
            (follower_id, followed_id, now),
        )
        conn.commit()
        return {"followed_id": followed_id, "following": True}
    finally:
        conn.close()


def unfollow_user(follower_id: str, followed_id: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM user_follows WHERE follower_id = ? AND followed_id = ?", (follower_id, followed_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_followed_users(follower_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT uf.followed_id, uf.created_at, u.email "
            "FROM user_follows uf JOIN users u ON u.id = uf.followed_id "
            "WHERE uf.follower_id = ? ORDER BY uf.created_at DESC",
            (follower_id,),
        ).fetchall()
        return [
            {"user_id": r["followed_id"], "handle": r["email"].split("@")[0], "created_at": r["created_at"]}
            for r in rows
        ]
    finally:
        conn.close()


def is_following_user(follower_id: str, followed_id: str) -> bool:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM user_follows WHERE follower_id = ? AND followed_id = ?", (follower_id, followed_id)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def follower_count(user_id: str) -> int:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT COUNT(*) AS n FROM user_follows WHERE followed_id = ?", (user_id,)
        ).fetchone()["n"]
    finally:
        conn.close()


def following_count(user_id: str) -> int:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT COUNT(*) AS n FROM user_follows WHERE follower_id = ?", (user_id,)
        ).fetchone()["n"]
    finally:
        conn.close()
