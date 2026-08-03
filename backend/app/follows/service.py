"""Series follows — the real personalization signal behind the "For You" tab.
See documentation/model_output_docs/FEED_SYSTEM_DESIGN.md (personalization_match
in the v1 ranking formula) and USER_PROFILES_AND_SOCIAL_DESIGN.md (follows).

User-to-user creator follows aren't built yet: feed_cards has no user_id
(community_post cards are seed/ingested content, not user-authored posts),
so following another user wouldn't affect anyone's feed today — it would be
a follow button that does nothing observable. Following a *series* does
something real right now: it's the input to for_you ranking below."""
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
