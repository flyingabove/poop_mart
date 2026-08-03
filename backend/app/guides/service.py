"""
Shake Guides — the box-shaking technique feature.
See documentation/model_output_docs/SHAKE_GUIDES_DESIGN.md.

Confidence scoring is intentionally simple for v1: it grows with contribution
count and net agreement (upvotes - downvotes), clamped to [0, 100]. A figure
signature backed by one claim should never look as trustworthy as one backed
by a dozen agreeing contributors.
"""
import time
from backend.app.db.database import get_connection


def _confidence(contribution_count: int, net_votes: int) -> int:
    return max(0, min(100, contribution_count * 12 + net_votes * 2))


def get_guide(series_id: str) -> dict | None:
    conn = get_connection()
    try:
        guide = conn.execute(
            "SELECT * FROM shake_guides WHERE series_id = ?", (series_id,)
        ).fetchone()
        if not guide:
            return None

        figures = conn.execute(
            "SELECT id, name FROM figures WHERE series_id = ?", (series_id,)
        ).fetchall()

        contributions = conn.execute(
            "SELECT * FROM guide_contributions WHERE guide_id = ? ORDER BY created_at DESC",
            (guide["id"],),
        ).fetchall()

        by_figure: dict[str, list] = {}
        for c in contributions:
            by_figure.setdefault(c["figure_id"], []).append(c)

        signatures = []
        for fig in figures:
            claims = by_figure.get(fig["id"], [])
            if not claims:
                continue
            weight_claim = next((c for c in claims if c["technique_type"] == "weight"), None)
            sound_claim = next((c for c in claims if c["technique_type"] == "sound"), None)
            net_votes = sum(c["upvotes"] - c["downvotes"] for c in claims)
            signatures.append({
                "figure_id": fig["id"],
                "figure_name": fig["name"],
                "weight_range_g": weight_claim["weight_range_g"] if weight_claim else None,
                "sound_description": sound_claim["claim_text"] if sound_claim else None,
                "contribution_count": len(claims),
                "confidence_score": _confidence(len(claims), net_votes),
            })
        signatures.sort(key=lambda s: s["confidence_score"], reverse=True)

        return {
            "series_id": guide["series_id"],
            "technique_summary": guide["technique_summary"],
            "etiquette_note": guide["etiquette_note"],
            "figure_signatures": signatures,
            "contributions": [
                {
                    "id": c["id"],
                    "figure_id": c["figure_id"],
                    "technique_type": c["technique_type"],
                    "claim_text": c["claim_text"],
                    "weight_range_g": c["weight_range_g"],
                    "upvotes": c["upvotes"],
                    "downvotes": c["downvotes"],
                    "video_url": c["video_url"],
                    "created_at": c["created_at"],
                }
                for c in contributions
            ],
        }
    finally:
        conn.close()


# Non-destructive technique types only — see the moderation scope in
# SHAKE_GUIDES_DESIGN.md. Anything outside this set is rejected, not just
# down-ranked.
_ALLOWED_TECHNIQUES = {"weight", "sound", "box_code", "seam"}


def add_contribution(
    series_id: str,
    figure_id: str,
    technique_type: str,
    claim_text: str,
    weight_range_g: str | None = None,
    video_url: str | None = None,
) -> dict:
    if technique_type not in _ALLOWED_TECHNIQUES:
        raise ValueError(f"technique_type must be one of {sorted(_ALLOWED_TECHNIQUES)}")

    conn = get_connection()
    try:
        guide = conn.execute(
            "SELECT id FROM shake_guides WHERE series_id = ?", (series_id,)
        ).fetchone()
        if not guide:
            now = int(time.time())
            guide_id = f"guide-{series_id}"
            conn.execute(
                "INSERT INTO shake_guides (id, series_id, technique_summary, created_at) VALUES (?, ?, ?, ?)",
                (guide_id, series_id, "Not enough contributions yet — be the first to add one.", now),
            )
        else:
            guide_id = guide["id"]

        now = int(time.time())
        cur = conn.execute(
            "INSERT INTO guide_contributions "
            "(guide_id, figure_id, technique_type, claim_text, weight_range_g, video_url, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (guide_id, figure_id, technique_type, claim_text, weight_range_g, video_url, now),
        )
        conn.commit()
        return {"id": cur.lastrowid, "guide_id": guide_id, "created_at": now}
    finally:
        conn.close()
