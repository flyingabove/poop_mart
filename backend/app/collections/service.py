"""User figure collections + valuation.
See documentation/model_output_docs/USER_PROFILES_AND_SOCIAL_DESIGN.md and
PRICE_TRACKING_DESIGN.md (valuation is documented there as a premium
feature — no billing system exists yet, so it's ungated for now).

acquired_at: DATA_MODEL_INVENTORY.md documents this as a first-class
CollectionItem field, but it was always silently set to "now" server-side
with no way for a client to provide a real acquisition date -- a real
gap for anyone backfilling an existing collection (most figures weren't
acquired the moment they're first logged in the app). add_item() now
accepts an optional client-provided acquired_at. Getting the upsert
right here matters: a condition-only edit (acquired_at not sent) must
NOT silently reset the item's acquisition date to today, so the
existing row's acquired_at is looked up first and reused unless the
caller explicitly provides a new one.
"""
import time

from backend.app.db.database import get_connection
from backend.app.pricing.service import get_current_price


class CollectionError(Exception):
    pass


def add_item(
    user_id: str,
    figure_id: str,
    condition: str | None = None,
    photo_url: str | None = None,
    acquired_at: int | None = None,
) -> dict:
    conn = get_connection()
    try:
        if not conn.execute("SELECT id FROM figures WHERE id = ?", (figure_id,)).fetchone():
            raise CollectionError("figure not found")

        existing = conn.execute(
            "SELECT acquired_at FROM collection_items WHERE user_id = ? AND figure_id = ?",
            (user_id, figure_id),
        ).fetchone()
        if acquired_at is not None:
            resolved_acquired_at = acquired_at
        elif existing is not None:
            resolved_acquired_at = existing["acquired_at"]
        else:
            resolved_acquired_at = int(time.time())

        conn.execute(
            "INSERT INTO collection_items (user_id, figure_id, condition, photo_url, acquired_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id, figure_id) DO UPDATE SET "
            "condition = excluded.condition, photo_url = excluded.photo_url, acquired_at = excluded.acquired_at",
            (user_id, figure_id, condition, photo_url, resolved_acquired_at),
        )
        conn.commit()
        return {
            "figure_id": figure_id,
            "condition": condition,
            "photo_url": photo_url,
            "acquired_at": resolved_acquired_at,
        }
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
