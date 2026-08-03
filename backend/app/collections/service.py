"""User figure collections + valuation.
See documentation/model_output_docs/USER_PROFILES_AND_SOCIAL_DESIGN.md and
PRICE_TRACKING_DESIGN.md (valuation is documented there as a premium
feature — no billing system exists yet, so it's ungated for now)."""
import time

from backend.app.db.database import get_connection
from backend.app.pricing.service import get_current_price


class CollectionError(Exception):
    pass


def add_item(user_id: str, figure_id: str, condition: str | None = None, photo_url: str | None = None) -> dict:
    conn = get_connection()
    try:
        if not conn.execute("SELECT id FROM figures WHERE id = ?", (figure_id,)).fetchone():
            raise CollectionError("figure not found")
        now = int(time.time())
        conn.execute(
            "INSERT INTO collection_items (user_id, figure_id, condition, photo_url, acquired_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id, figure_id) DO UPDATE SET "
            "condition = excluded.condition, photo_url = excluded.photo_url",
            (user_id, figure_id, condition, photo_url, now),
        )
        conn.commit()
        return {"figure_id": figure_id, "condition": condition, "photo_url": photo_url, "acquired_at": now}
    finally:
        conn.close()


def remove_item(user_id: str, figure_id: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM collection_items WHERE user_id = ? AND figure_id = ?", (user_id, figure_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_collection(user_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT ci.figure_id, ci.condition, ci.photo_url, ci.acquired_at, f.name, f.series_id "
            "FROM collection_items ci JOIN figures f ON f.id = ci.figure_id "
            "WHERE ci.user_id = ? ORDER BY ci.acquired_at DESC",
            (user_id,),
        ).fetchall()
        items = []
        for r in rows:
            price = get_current_price(r["figure_id"])
            items.append({
                "figure_id": r["figure_id"],
                "figure_name": r["name"],
                "series_id": r["series_id"],
                "condition": r["condition"],
                "photo_url": r["photo_url"],
                "acquired_at": r["acquired_at"],
                "current_price": price["median_price"] if price else None,
            })
        return items
    finally:
        conn.close()


def get_valuation(user_id: str) -> dict:
    items = list_collection(user_id)
    priced = [i for i in items if i["current_price"] is not None]
    return {
        "total_value": round(sum(i["current_price"] for i in priced), 2),
        "figure_count": len(items),
        "priced_figure_count": len(priced),
    }
