"""
Search. See documentation/model_output_docs/SEARCH_DESIGN.md.

v1 is a substring match over the series/figure alias table in SQLite — the
real design calls for Elasticsearch/OpenSearch with fuzzy matching once there's
enough content volume to need it (see TECH_STACK_AND_INFRASTRUCTURE.md).
"""
from backend.app.db.database import get_connection


def search(query: str, limit: int = 20) -> dict:
    q = f"%{query.lower()}%"
    conn = get_connection()
    try:
        series = conn.execute(
            "SELECT id, name, brand_line FROM series "
            "WHERE lower(name) LIKE ? OR lower(aliases) LIKE ? OR lower(brand_line) LIKE ? LIMIT ?",
            (q, q, q, limit),
        ).fetchall()
        figures = conn.execute(
            "SELECT id, name, series_id FROM figures WHERE lower(name) LIKE ? LIMIT ?",
            (q, limit),
        ).fetchall()
        return {
            "series": [{"id": r["id"], "name": r["name"], "brand_line": r["brand_line"]} for r in series],
            "figures": [{"id": r["id"], "name": r["name"], "series_id": r["series_id"]} for r in figures],
        }
    finally:
        conn.close()
