def _auth_headers(client, email="reviewer1@example.com"):
    r = client.post("/api/auth/signup", json={"email": email, "password": "hunter2222"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_get_reviews_empty_for_unreviewed_figure(client):
    r = client.get("/api/figures/cb-tears/reviews")
    assert r.status_code == 200
    data = r.json()
    assert data["review_count"] == 0
    assert data["average_rating"] is None
    assert data["reviews"] == []
    assert data["my_review"] is None


def test_post_review_requires_auth(client):
    r = client.post("/api/figures/lfp-forest-ranger/reviews", json={"rating": 5})
    assert r.status_code == 401


def test_post_and_list_review(client):
    headers = _auth_headers(client, "reviewer2@example.com")
    r = client.post(
        "/api/figures/lfp-forest-ranger/reviews",
        json={"rating": 4, "text": "Great paint job, box was a little dented."},
        headers=headers,
    )
    assert r.status_code == 201

    data = client.get("/api/figures/lfp-forest-ranger/reviews").json()
    assert data["review_count"] == 1
    assert data["average_rating"] == 4.0
    assert data["reviews"][0]["rating"] == 4
    assert data["reviews"][0]["reviewer"] == "reviewer2"  # local part of the email, not the full address
    assert "@" not in data["reviews"][0]["reviewer"]


def test_review_rejects_out_of_range_rating(client):
    headers = _auth_headers(client, "reviewer3@example.com")
    r = client.post("/api/figures/lfp-forest-ranger/reviews", json={"rating": 6}, headers=headers)
    assert r.status_code == 422
    r2 = client.post("/api/figures/lfp-forest-ranger/reviews", json={"rating": 0}, headers=headers)
    assert r2.status_code == 422


def test_review_unknown_figure_422s(client):
    headers = _auth_headers(client, "reviewer4@example.com")
    r = client.post("/api/figures/does-not-exist/reviews", json={"rating": 5}, headers=headers)
    assert r.status_code == 422


def test_posting_again_updates_not_duplicates(client):
    headers = _auth_headers(client, "reviewer5@example.com")
    client.post("/api/figures/cb-tears/reviews", json={"rating": 2, "text": "meh"}, headers=headers)
    client.post("/api/figures/cb-tears/reviews", json={"rating": 5, "text": "actually great"}, headers=headers)

    data = client.get("/api/figures/cb-tears/reviews").json()
    mine = [r for r in data["reviews"] if r["reviewer"] == "reviewer5"]
    assert len(mine) == 1
    assert mine[0]["rating"] == 5
    assert mine[0]["text"] == "actually great"


def test_my_review_reflects_own_submission(client):
    headers = _auth_headers(client, "reviewer6@example.com")
    client.post("/api/figures/lm-vanilla/reviews", json={"rating": 3, "text": "ok"}, headers=headers)

    data = client.get("/api/figures/lm-vanilla/reviews", headers=headers).json()
    assert data["my_review"] == {"rating": 3, "text": "ok"}

    # anonymous request to the same figure shouldn't see a my_review
    anon_data = client.get("/api/figures/lm-vanilla/reviews").json()
    assert anon_data["my_review"] is None


def test_average_rating_across_multiple_reviewers(client):
    figure_id = "sp-nightwatch"
    headers_a = _auth_headers(client, "avg-a@example.com")
    headers_b = _auth_headers(client, "avg-b@example.com")
    client.post(f"/api/figures/{figure_id}/reviews", json={"rating": 2}, headers=headers_a)
    client.post(f"/api/figures/{figure_id}/reviews", json={"rating": 4}, headers=headers_b)

    data = client.get(f"/api/figures/{figure_id}/reviews").json()
    assert data["review_count"] == 2
    assert data["average_rating"] == 3.0


def test_delete_review(client):
    headers = _auth_headers(client, "reviewer7@example.com")
    client.post("/api/figures/lm-vanilla/reviews", json={"rating": 5}, headers=headers)

    r = client.delete("/api/figures/lm-vanilla/reviews", headers=headers)
    assert r.status_code == 200

    data = client.get("/api/figures/lm-vanilla/reviews", headers=headers).json()
    assert data["my_review"] is None


def test_delete_nonexistent_review_404s(client):
    headers = _auth_headers(client, "reviewer8@example.com")
    r = client.delete("/api/figures/lm-vanilla/reviews", headers=headers)
    assert r.status_code == 404
