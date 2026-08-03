"""
Search. See documentation/model_output_docs/SEARCH_DESIGN.md.

v1 was a plain SQL LIKE substring match with no typo tolerance. This adds a
fuzzy fallback via difflib (stdlib, no new dependency) so "Skullpanada" or
"Croybaby" still finds "Skullpanda" / "Crybaby" -- exact/substring hits
always rank first, fuzzy hits fill in after, and nothing appears twice.

True cross-language matching (e.g. a Chinese name resolving to the English
catalog entry) is a separate, larger effort -- it needs a real alias/
translation table, not a string-similarity trick -- and isn't attempted
here. The real design (per TECH_STACK_AND_INFRASTRUCTURE.md) is
Elasticsearch/OpenSearch once there's enough content volume to justify it;
this is the honest, dependency-free v1 in the meantime.

The Index section also names "free-text search over community posts,
reviews, and guide content" -- only posts are implemented so far
(_search_posts, plain substring match, no fuzzy fallback since post
text is long-form and typos matter far less than in a short figure
name). Reviews and guide contribution text are the same real gap,
left for a follow-up rather than done sloppily in the same pass.
"""
import difflib

from backend.app.db.database import get_connection

_FUZZY_THRESHOLD = 0.6


def _substring_matches(query: str, series: list, figures: list) -> tuple[list, list]:
    q = query.lower()
    series_hits = [
        s
        for s in series
        if q in s["name"].lower() or q in (s["aliases"] or "").lower() or q in s["brand_line"].lower()
    ]
    figure_hits = [f for f in figures if q in f["name"].lower()]
    return series_hits, figure_hits


def _fuzzy_matches(
    query: str, series: list, figures: list, exclude_series_ids: set, exclude_figure_ids: set
) -> tuple[list, list]:
    q = query.lower()

    scored_series = []
    for s in series:
        if s["id"] in exclude_series_ids:
            continue
        candidates = [s["name"].lower(), s["brand_line"].lower()] + [
            a.strip().lower() for a in (s["aliases"] or "").split(",") if a.strip()
        ]
        best = max((difflib.SequenceMatcher(None, q, c).ratio() for c in candidates), default=0.0)
        if best >= _FUZZY_THRESHOLD:
            scored_series.append((best, s))

    scored_figures = []
    for f in figures:
        if f["id"] in exclude_figure_ids:
            continue
        ratio = difflib.SequenceMatcher(None, q, f["name"].lower()).ratio()
        if ratio >= _FUZZY_THRESHOLD:
            scored_figures.append((ratio, f))

    scored_series.sort(key=lambda pair: pair[0], reverse=True)
    scored_figures.sort(key=lambda pair: pair[0], reverse=True)
    return [s for _, s in scored_series], [f for _, f in scored_figures]


def _search_posts(conn, query: str, limit: int) -> list[dict]:
    like = f"%{query.lower()}%"
    rows = conn.execute(
        "SELECT fc.id, fc.title, fc.figure_id, f.name AS figure_name, u.email AS poster_email "
        "FROM feed_cards fc "
        "JOIN figures f ON f.id = fc.figure_id "
        "LEFT JOIN users u ON u.id = fc.user_id "
        "WHERE fc.card_type = 'community_post' "
        "AND (LOWER(fc.title) LIKE ? OR LOWER(fc.body) LIKE ?) "
        "ORDER BY fc.created_at DESC LIMIT ?",
        (like, like, limit),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "figure_id": r["figure_id"],
            "figure_name": r["figure_name"],
            "poster": r["poster_email"].split("@")[0] if r["poster_email"] else None,
        }
        for r in rows
    ]


def search(query: str, limit: int = 20) -> dict:
    conn = get_connection()
    try:
        series = [dict(r) for r in conn.execute("SELECT id, name, aliases, brand_line FROM series")]
        figures = [dict(r) for r in conn.execute("SELECT id, name, series_id FROM figures")]

        series_hits, figure_hits = _substring_matches(query, series, figures)
        exclude_series_ids = {s["id"] for s in series_hits}
        exclude_figure_ids = {f["id"] for f in figure_hits}
        fuzzy_series, fuzzy_figures = _fuzzy_matches(query, series, figures, exclude_series_ids, exclude_figure_ids)

        all_series = (series_hits + fuzzy_series)[:limit]
        all_figures = (figure_hits + fuzzy_figures)[:limit]

        return {
            "series": [{"id": s["id"], "name": s["name"], "brand_line": s["brand_line"]} for s in all_series],
            "figures": [{"id": f["id"], "name": f["name"], "series_id": f["series_id"]} for f in all_figures],
            "posts": _search_posts(conn, query, limit),
        }
    finally:
        conn.close()
