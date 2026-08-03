def _signup(client, email):
    r = client.post("/api/auth/signup", json={"email": email, "password": "hunter2222"})
    data = r.json()
    return data["user_id"], {"Authorization": f"Bearer {data['access_token']}"}


def test_profile_unknown_user_404s(client):
    r = client.get("/api/users/does-not-exist/profile")
    assert r.status_code == 404


def test_profile_shape_for_fresh_user(client):
    user_id, _headers = _signup(client, "profile-fresh@example.com")
    r = client.get(f"/api/users/{user_id}/profile")
    assert r.status_code == 200
    data = r.json()
    assert data["user_id"] == user_id
    assert data["handle"] == "profile-fresh"
    # Early Adopter is earned by signup order alone (see badges/service.py),
    # so a fresh test-suite signup legitimately gets it -- only assert the
    # *earned-by-activity* badges are absent, not that the list is empty.
    badge_codes = {b["code"] for b in data["badges"]}
    assert "guide_contributor" not in badge_codes
    assert "top_reviewer" not in badge_codes
    assert data["follower_count"] == 0
    assert data["following_count"] == 0
    assert data["viewer_is_following"] is False
    assert data["rankings"] == []
    assert data["posts"] == []
    assert data["reviews"] == []


def test_profile_is_public_no_auth_required(client):
    user_id, _headers = _signup(client, "profile-public@example.com")
    r = client.get(f"/api/users/{user_id}/profile")
    assert r.status_code == 200


def test_profile_shows_own_rankings_posts_and_reviews(client):
    user_id, headers = _signup(client, "profile-content@example.com")
    client.post("/api/rankings", json={"title": "Profile Ranking"}, headers=headers)
    client.post(
        "/api/feed/posts",
        json={"figure_id": "lfp-forest-ranger", "title": "Profile Post", "body": "look at this"},
        headers=headers,
    )
    client.post(
        "/api/figures/lfp-mushroom-nap/reviews",
        json={"rating": 4, "text": "Solid figure"},
        headers=headers,
    )

    data = client.get(f"/api/users/{user_id}/profile").json()
    assert any(rk["title"] == "Profile Ranking" for rk in data["rankings"])
    post = next(p for p in data["posts"] if p["title"] == "Profile Post")
    assert post["figure_id"] == "lfp-forest-ranger"
    assert post["figure_name"] == "Forest Ranger"
    review = next(r for r in data["reviews"] if r["figure_id"] == "lfp-mushroom-nap")
    assert review["rating"] == 4
    assert review["text"] == "Solid figure"
    assert review["figure_name"] == "Mushroom Nap"


def test_profile_follower_and_following_counts_update(client):
    a_id, a_headers = _signup(client, "profile-count-a@example.com")
    b_id, b_headers = _signup(client, "profile-count-b@example.com")

    client.post(f"/api/follows/users/{b_id}", headers=a_headers)

    a_profile = client.get(f"/api/users/{a_id}/profile").json()
    b_profile = client.get(f"/api/users/{b_id}/profile").json()
    assert a_profile["following_count"] == 1
    assert a_profile["follower_count"] == 0
    assert b_profile["follower_count"] == 1
    assert b_profile["following_count"] == 0


def test_profile_viewer_is_following_reflects_logged_in_viewer(client):
    a_id, a_headers = _signup(client, "profile-viewer-a@example.com")
    b_id, b_headers = _signup(client, "profile-viewer-b@example.com")

    client.post(f"/api/follows/users/{b_id}", headers=a_headers)

    as_a = client.get(f"/api/users/{b_id}/profile", headers=a_headers).json()
    assert as_a["viewer_is_following"] is True

    as_b = client.get(f"/api/users/{b_id}/profile", headers=b_headers).json()
    assert as_b["viewer_is_following"] is False  # can't follow yourself

    anonymous = client.get(f"/api/users/{b_id}/profile").json()
    assert anonymous["viewer_is_following"] is False
