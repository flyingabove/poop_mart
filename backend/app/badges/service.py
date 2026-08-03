"""
Badges — earned reputation markers, computed on read (not stored or
materialized in a table). See
documentation/model_output_docs/USER_PROFILES_AND_SOCIAL_DESIGN.md.

Only badges computable from data that genuinely exists are implemented:
Guide Contributor (guide_contributions.user_id, real since iteration 12),
Top Reviewer (reviews.user_id + review_votes, real since iteration 30 --
see below), and Early Adopter (users.created_at, real since iteration 1).
"Verified Creator" is deliberately NOT implemented -- the design doc
describes it as a manual/verified-account process, and there's no admin
or verification flow in this app. Auto-granting it to satisfy the badge
list would misrepresent what the badge is supposed to mean, so it's left
out rather than faked.

Top Reviewer: the design doc defines this as review volume *and*
helpfulness votes, but for a long time only volume was implemented --
review_votes existed (iteration 9) but was never actually checked here.
Fixed at iteration 30 by additionally requiring net helpful votes
(helpful - unhelpful, summed across all of a user's reviews) to be
strictly positive. Chose >=1 net rather than a higher number: it's the
smallest bar that actually means something ("the community found at
least one of your reviews net-helpful"), and picking a bigger arbitrary
number would need real usage data to size correctly, same reasoning
MONETIZATION.md gives for deferring the subscription tier question.
"""
from backend.app.db.database import get_connection

GUIDE_CONTRIBUTOR_THRESHOLD = 3
TOP_REVIEWER_THRESHOLD = 3
TOP_REVIEWER_MIN_NET_HELPFUL = 1
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

        review_row = conn.execute(
            "SELECT COUNT(DISTINCT r.id) AS review_count, "
            "COALESCE(SUM(CASE rv.direction WHEN 'helpful' THEN 1 WHEN 'unhelpful' THEN -1 ELSE 0 END), 0) AS net_helpful "
            "FROM reviews r LEFT JOIN review_votes rv ON rv.review_id = r.id "
            "WHERE r.user_id = ?",
            (user_id,),
        ).fetchone()
        review_count, net_helpful = review_row["review_count"], review_row["net_helpful"]
        if review_count >= TOP_REVIEWER_THRESHOLD and net_helpful >= TOP_REVIEWER_MIN_NET_HELPFUL:
            badges.append({
                "code": "top_reviewer",
                "label": "Top Reviewer",
                "description": f"Written {review_count} figure reviews, net +{net_helpful} helpful votes.",
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
