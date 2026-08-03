"""
Shake Guides — the box-shaking technique feature.
See documentation/model_output_docs/SHAKE_GUIDES_DESIGN.md.

Confidence scoring is intentionally simple for v1: it grows with contribution
count and net agreement (upvotes - downvotes), clamped to [0, 100]. A figure
signature backed by one claim should never look as trustworthy as one backed
by a dozen agreeing contributors.

Voting: real per-user votes live in `contribution_votes` (one vote per user
per contribution, changeable). The seeded contributions' `upvotes`/
`downvotes` columns predate real voting and are kept as a baseline offset
rather than replaced -- switching wholesale to a votes-derived count would
zero out the flagship demo guide's confidence scores, since the seed data
has no corresponding contribution_votes rows. Displayed/scored vote counts
are baseline + real votes, added together.

Contribution authorship: `guide_contributions.user_id` is nullable --
seed-era contributions predate auth and have no attributable user, and
that's not backfilled. New contributions require a logged-in user (see
api/guides.py), matching voting's existing auth requirement -- posting a
contribution anonymously while voting on it required login was an
inconsistency, and anonymous authorship also made a real "Guide
Contributor" badge impossible to compute honestly.
"""
import time
from backend.app.db.database import get_connection


def _display_handle(email: str | None) -> str | None:
    return email.split("@")[0] if email else None


def _confidence(contribution_count: int, net_votes: int) -> int:
    return max(0, min(100, contribution_count * 12 + net_votes * 2))


def get_guide(series_id: str, user_id: str | None = None) -> dict | None:
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
            "SELECT gc.*, u.email AS contributor_email FROM guide_contributions gc "
            "LEFT JOIN users u ON u.id = gc.user_id "
            "WHERE gc.guide_id = ? ORDER BY gc.created_at DESC",
            (guide["id"],),
        ).fetchall()

        vote_rows = conn.execute(
            "SELECT contribution_id, "
            "SUM(CASE WHEN direction = 'up' THEN 1 ELSE 0 END) AS up, "
            "SUM(CASE WHEN direction = 'down' THEN 1 ELSE 0 END) AS down "
            "FROM contribution_votes "
            "WHERE contribution_id IN (SELECT id FROM guide_contributions WHERE guide_id = ?) "
            "GROUP BY contribution_id",
            (guide["id"],),
        ).fetchall()
        vote_deltas = {r["contribution_id"]: (r["up"] or 0, r["down"] or 0) for r in vote_rows}

        my_votes: dict[int, str] = {}
        if user_id:
            my_vote_rows = conn.execute(
                "SELECT contribution_id, direction FROM contribution_votes "
                "WHERE user_id = ? AND contribution_id IN (SELECT id FROM guide_contributions WHERE guide_id = ?)",
                (user_id, guide["id"]),
            ).fetchall()
            my_votes = {r["contribution_id"]: r["direction"] for r in my_vote_rows}

        def _total_votes(c) -> tuple[int, int]:
            up_delta, down_delta = vote_deltas.get(c["id"], (0, 0))
            return c["upvotes"] + up_delta, c["downvotes"] + down_delta

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
            net_votes = 0
            for c in claims:
                up, down = _total_votes(c)
                net_votes += up - down
            signatures.append({
                "figure_id": fig["id"],
                "figure_name": fig["name"],
                "weight_range_g": weight_claim["weight_range_g"] if weight_claim else None,
                "sound_description": sound_claim["claim_text"] if sound_claim else None,
                "contribution_count": len(claims),
                "confidence_score": _confidence(len(claims), net_votes),
            })
        signatures.sort(key=lambda s: s["confidence_score"], reverse=True)

        contribution_dicts = []
        for c in contributions:
            up, down = _total_votes(c)
            contribution_dicts.append({
                "id": c["id"],
                "figure_id": c["figure_id"],
                "technique_type": c["technique_type"],
                "claim_text": c["claim_text"],
                "weight_range_g": c["weight_range_g"],
                "upvotes": up,
                "downvotes": down,
                "video_url": c["video_url"],
                "created_at": c["created_at"],
                "my_vote": my_votes.get(c["id"]),
                "contributor": _display_handle(c["contributor_email"]),
            })

        return {
            "series_id": guide["series_id"],
            "technique_summary": guide["technique_summary"],
            "etiquette_note": guide["etiquette_note"],
            "figure_signatures": signatures,
            "contributions": contribution_dicts,
        }
    finally:
        conn.close()


_ALLOWED_VOTE_DIRECTIONS = {"up", "down"}


def vote_contribution(user_id: str, contribution_id: int, direction: str) -> dict:
    if direction not in _ALLOWED_VOTE_DIRECTIONS:
        raise ValueError(f"direction must be one of {sorted(_ALLOWED_VOTE_DIRECTIONS)}")

    conn = get_connection()
    try:
        if not conn.execute(
            "SELECT id FROM guide_contributions WHERE id = ?", (contribution_id,)
        ).fetchone():
            raise ValueError("contribution not found")

        now = int(time.time())
        conn.execute(
            "INSERT INTO contribution_votes (user_id, contribution_id, direction, created_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id, contribution_id) DO UPDATE SET "
            "direction = excluded.direction, created_at = excluded.created_at",
            (user_id, contribution_id, direction, now),
        )
        conn.commit()

        row = conn.execute(
            "SELECT "
            "SUM(CASE WHEN direction = 'up' THEN 1 ELSE 0 END) AS up, "
            "SUM(CASE WHEN direction = 'down' THEN 1 ELSE 0 END) AS down "
            "FROM contribution_votes WHERE contribution_id = ?",
            (contribution_id,),
        ).fetchone()
        base = conn.execute(
            "SELECT upvotes, downvotes FROM guide_contributions WHERE id = ?", (contribution_id,)
        ).fetchone()
        return {
            "contribution_id": contribution_id,
            "my_vote": direction,
            "upvotes": base["upvotes"] + (row["up"] or 0),
            "downvotes": base["downvotes"] + (row["down"] or 0),
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
    user_id: str,
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
            "(guide_id, figure_id, technique_type, claim_text, weight_range_g, video_url, user_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (guide_id, figure_id, technique_type, claim_text, weight_range_g, video_url, user_id, now),
        )
        conn.commit()
        return {"id": cur.lastrowid, "guide_id": guide_id, "created_at": now}
    finally:
        conn.close()
