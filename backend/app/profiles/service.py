"""
Public collector profile -- aggregates data other domains already expose
per-user into one public-read view. See
documentation/model_output_docs/USER_PROFILES_AND_SOCIAL_DESIGN.md.

Deliberately scoped to what's genuinely public and queryable today:
handle, badges, follower/following counts, public rankings, and
community posts (pulls). Collection showcase and a per-user review
listing are real doc'd profile content too, but are left for a
follow-up -- collection_items has no privacy field yet (shipping it now
would mean everyone's full collection defaults to public with no choice
in the matter), and reviews has no list-by-user query yet. Shipping the
parts that are unambiguous now rather than guessing at a privacy default
nobody asked for.
"""
from backend.app.badges.service import get_badges
from backend.app.db.database import get_connection
from backend.app.feed.service import list_posts_by_user
from backend.app.follows.service import follower_count, following_count, is_following_user
from backend.app.rankings.service import list_rankings


def get_profile(user_id: str, viewer_id: str | None = None) -> dict | None:
    conn = get_connection()
    try:
        user = conn.execute("SELECT id, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return None
    finally:
        conn.close()

    viewer_is_following = False
    if viewer_id and viewer_id != user_id:
        viewer_is_following = is_following_user(viewer_id, user_id)

    return {
        "user_id": user_id,
        "handle": user["email"].split("@")[0],
        "member_since": user["created_at"],
        "badges": get_badges(user_id),
        "follower_count": follower_count(user_id),
        "following_count": following_count(user_id),
        "viewer_is_following": viewer_is_following,
        "rankings": list_rankings(user_id),
        "posts": list_posts_by_user(user_id),
    }
