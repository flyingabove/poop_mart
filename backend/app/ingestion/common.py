"""Shared helpers for ingestion connectors (news.py, youtube.py) -- both
need to map a headline/video title to a known figure or series before
inserting a feed card. Extracted here once youtube.py needed the exact
same logic as news.py's original _load_catalog()/_resolve() -- real
duplication across two live connectors, not a speculative abstraction."""
from backend.app.db.database import get_connection


def load_catalog(conn) -> tuple[list[dict], list[dict]]:
    series = [dict(r) for r in conn.execute("SELECT id, name, aliases FROM series")]
    figures = [dict(r) for r in conn.execute("SELECT id, name, series_id FROM figures")]
    return series, figures


def resolve_title(title: str, series: list[dict], figures: list[dict]) -> tuple[str | None, str | None]:
    """Best-effort match a headline/title to a known figure/series by
    substring -- the same alias-table resolution approach described in
    TREND_DETECTION_DESIGN.md, just without a real NLP layer yet.

    Leaves both None rather than guessing when nothing matches: an
    unlinked card still renders fine in the feed, a wrongly-linked one
    actively misleads whoever reads it on a figure's page.
    """
    t = title.lower()
    for fig in figures:
        if fig["name"].lower() in t:
            return fig["id"], fig["series_id"]
    for s in series:
        aliases = [a.strip().lower() for a in (s["aliases"] or "").split(",") if a.strip()]
        if any(name in t for name in [s["name"].lower(), *aliases]):
            return None, s["id"]
    return None, None
