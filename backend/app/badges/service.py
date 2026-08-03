"""
Badges — earned reputation markers, computed on read (not stored or
materialized in a table). See
documentation/model_output_docs/USER_PROFILES_AND_SOCIAL_DESIGN.md.

Only badges computable from data that genuinely exists are implemented:
Guide Contributor (guide_contributions.user_id, real since iteration 12),
Top Reviewer (reviews.user_id, real since iteration 7), and Early Adopter
(users.created_at, real since iteration 1). "Verified Creator" is
deliberately NOT implemented -- the design doc describes it as a manual/
verified-account process, and there's no admin or verification flow in
this app. Auto-granting it to satisfy the badge list would misrepresent
what the badge is supposed to mean, so it's left out rather than faked.
"""
from backend.app.db.database import get_connection

GUIDE_CONTRIBUTOR_THRESHOLD = 3
TOP_REVIEWER_THRESHOLD = 3
EARLY_ADOPTER_RANK_CUTOFF = 100


def get_badges(user_id: str) -> list[dict]:
    conn = get_connection()
    try:
        badges = []

        contrib_count = conn.execute(
            "SELECT COUNT(*) AS n FROM guide_contributions WHERE user_id = ?", (user_id,)
        ).fetchone()["n"]
        if contrib_count >= GUIDE_CONTRIBUTOR_THRESHOLD:
            badges.append({
                "code": "guide_contributor",
                "label": "Guide Contributor",
                "description": f"Contributed {contrib_count} tells to Shake Guides.",
            })

        review_count = conn.execute(
            "SELECT COUNT(*) AS n FROM reviews WHERE user_id = ?", (user_id,)
        ).fetchone()["n"]
        if review_count >= TOP_REVIEWER_THRESHOLD:
            badges.append({
                "code": "top_reviewer",
                "label": "Top Reviewer",
                "description": f"Written {review_count} figure reviews.",
            })

        user_row = conn.execute("SELECT created_at FROM users WHERE id = ?", (user_id,)).fetchone()
        if user_row:
            # Rank by signup order (ties count together, which is fine for a
            # threshold badge -- doesn't need strict, unique ranking).
            rank = conn.execute(
                "SELECT COUNT(*) AS n FROM users WHERE created_at <= ?", (user_row["created_at"],)
            ).fetchone()["n"]
            if rank <= EARLY_ADOPTER_RANK_CUTOFF:
                badges.append({
                    "code": "early_adopter",
                    "label": "Early Adopter",
                    "description": f"One of the first {EARLY_ADOPTER_RANK_CUTOFF} PoopMart accounts.",
                })

        return badges
    finally:
        conn.close()
