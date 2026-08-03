"""Repository classes for the figure/series catalog."""
from backend.app.db.database import get_connection


class CatalogRepo:
    @staticmethod
    def list_series() -> list[dict]:
        conn = get_connection()
        try:
            rows = conn.execute("SELECT * FROM series ORDER BY name").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def get_series(series_id: str) -> dict | None:
        conn = get_connection()
        try:
            row = conn.execute("SELECT * FROM series WHERE id = ?", (series_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def list_figures(series_id: str | None = None) -> list[dict]:
        conn = get_connection()
        try:
            if series_id:
                rows = conn.execute(
                    "SELECT * FROM figures WHERE series_id = ? ORDER BY name", (series_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM figures ORDER BY name").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def get_figure(figure_id: str) -> dict | None:
        conn = get_connection()
        try:
            row = conn.execute("SELECT * FROM figures WHERE id = ?", (figure_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
