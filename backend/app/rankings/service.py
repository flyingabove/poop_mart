"""
User-curated ranked figure lists ("My Top 10 Forest Party Figures").
See documentation/model_output_docs/USER_PROFILES_AND_SOCIAL_DESIGN.md
(user-curated top-N lists) -- fully documented there since the original
session, never built until now.

v1 ordering is simply insertion order (when an item was added) -- no
explicit drag-to-reorder position field. Removing and re-adding an item
moves it to the end, which is the only way to reorder for now. A real
position/reorder mechanism is a reasonable follow-up once this is used
enough to need it; not worth the added complexity for a first version.

Rankings are publicly viewable by ID (this is profile content meant to be
shown to others, per the design doc) but only the owner can create,
modify, or delete their own -- same public-read/owner-write shape as
reviews and collections elsewhere in this app.
"""
import time

from backend.app.db.database import get_connection


class RankingError(Exception):
    pass


def create_ranking(user_id: str, title: str) -> dict:
    title = title.strip()
    if not title:
        raise RankingError("title is required")

    conn = get_connection()
    try:
        now = int(time.time())
        cur = conn.execute(
            "INSERT INTO rankings (user_id, title, created_at) VALUES (?, ?, ?)",
            (user_id, title, now),
        )
        conn.commit()
        return {"id": cur.lastrowid, "title": title, "created_at": now}
    finally:
        conn.close()


def list_rankings(user_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT r.id, r.title, r.created_at, COUNT(ri.id) AS item_count "
            "FROM rankings r LEFT JOIN ranking_items ri ON ri.ranking_id = r.id "
            "WHERE r.user_id = ? GROUP BY r.id ORDER BY r.created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_ranking(ranking_id: int) -> dict | None:
    conn = get_connection()
    try:
        ranking = conn.execute(
            "SELECT r.id, r.title, r.created_at, r.user_id, u.email "
            "FROM rankings r JOIN users u ON u.id = r.user_id WHERE r.id = ?",
            (ranking_id,),
        ).fetchone()
        if not ranking:
            return None

        items = conn.execute(
            "SELECT ri.figure_id, f.name, f.series_id "
            "FROM ranking_items ri JOIN figures f ON f.id = ri.figure_id "
            "WHERE ri.ranking_id = ? ORDER BY ri.created_at ASC",
            (ranking_id,),
        ).fetchall()

        return {
            "id": ranking["id"],
            "title": ranking["title"],
            "created_at": ranking["created_at"],
            "owner": ranking["email"].split("@")[0],
            "owner_id": ranking["user_id"],
            "items": [
                {"figure_id": r["figure_id"], "figure_name": r["name"], "series_id": r["series_id"]}
                for r in items
            ],
        }
    finally:
        conn.close()


def delete_ranking(user_id: str, ranking_id: int) -> bool:
    conn = get_connection()
    try:
        row = conn.execute("SELECT user_id FROM rankings WHERE id = ?", (ranking_id,)).fetchone()
        if not row or row["user_id"] != user_id:
            return False
        conn.execute("DELETE FROM ranking_items WHERE ranking_id = ?", (ranking_id,))
        conn.execute("DELETE FROM rankings WHERE id = ?", (ranking_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def add_item(user_id: str, ranking_id: int, figure_id: str) -> dict:
    conn = get_connection()
    try:
        ranking = conn.execute("SELECT user_id FROM rankings WHERE id = ?", (ranking_id,)).fetchone()
        if not ranking or ranking["user_id"] != user_id:
            raise RankingError("ranking not found")
        if not conn.execute("SELECT id FROM figures WHERE id = ?", (figure_id,)).fetchone():
            raise RankingError("figure not found")

        now = int(time.time())
        conn.execute(
            "INSERT OR IGNORE INTO ranking_items (ranking_id, figure_id, created_at) VALUES (?, ?, ?)",
            (ranking_id, figure_id, now),
        )
        conn.commit()
        return {"ranking_id": ranking_id, "figure_id": figure_id}
    finally:
        conn.close()


def remove_item(user_id: str, ranking_id: int, figure_id: str) -> bool:
    conn = get_connection()
    try:
        ranking = conn.execute("SELECT user_id FROM rankings WHERE id = ?", (ranking_id,)).fetchone()
        if not ranking or ranking["user_id"] != user_id:
            return False
        cur = conn.execute(
            "DELETE FROM ranking_items WHERE ranking_id = ? AND figure_id = ?", (ranking_id, figure_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
