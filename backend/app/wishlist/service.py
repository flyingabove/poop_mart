"""Wishlists + price-drop alert thresholds.
See documentation/model_output_docs/PRICE_TRACKING_DESIGN.md."""
import time

from backend.app.db.database import get_connection
from backend.app.pricing.service import get_current_price


class WishlistError(Exception):
    pass


def add_item(user_id: str, figure_id: str, alert_threshold: float | None = None) -> dict:
    conn = get_connection()
    try:
        if not conn.execute("SELECT id FROM figures WHERE id = ?", (figure_id,)).fetchone():
            raise WishlistError("figure not found")
        now = int(time.time())
        conn.execute(
            "INSERT INTO wishlist_items (user_id, figure_id, alert_threshold, created_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id, figure_id) DO UPDATE SET alert_threshold = excluded.alert_threshold",
            (user_id, figure_id, alert_threshold, now),
        )
        conn.commit()
        return {"figure_id": figure_id, "alert_threshold": alert_threshold}
    finally:
        conn.close()


def remove_item(user_id: str, figure_id: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM wishlist_items WHERE user_id = ? AND figure_id = ?", (user_id, figure_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_wishlist(user_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT wi.figure_id, wi.alert_threshold, wi.created_at, f.name, f.series_id "
            "FROM wishlist_items wi JOIN figures f ON f.id = wi.figure_id "
            "WHERE wi.user_id = ? ORDER BY wi.created_at DESC",
            (user_id,),
        ).fetchall()
        items = []
        for r in rows:
            price = get_current_price(r["figure_id"])
            current_price = price["median_price"] if price else None
            below_threshold = (
                r["alert_threshold"] is not None
                and current_price is not None
                and current_price <= r["alert_threshold"]
            )
            items.append({
                "figure_id": r["figure_id"],
                "figure_name": r["name"],
                "series_id": r["series_id"],
                "alert_threshold": r["alert_threshold"],
                "current_price": current_price,
                "below_threshold": below_threshold,
                "created_at": r["created_at"],
            })
        return items
    finally:
        conn.close()
