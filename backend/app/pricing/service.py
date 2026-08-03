"""Price tracking / valuation. See documentation/model_output_docs/PRICE_TRACKING_DESIGN.md."""
from backend.app.db.database import get_connection


def get_price_history(figure_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT timestamp, median_price, low_price, high_price, listing_count, source "
            "FROM price_snapshots WHERE figure_id = ? ORDER BY timestamp ASC",
            (figure_id,),
        ).fetchall()
        return [
            {
                "timestamp": r["timestamp"],
                "median_price": r["median_price"],
                "low_price": r["low_price"],
                "high_price": r["high_price"],
                "listing_count": r["listing_count"],
                "source": r["source"],
            }
            for r in rows
        ]
    finally:
        conn.close()


def get_current_price(figure_id: str) -> dict | None:
    history = get_price_history(figure_id)
    return history[-1] if history else None
