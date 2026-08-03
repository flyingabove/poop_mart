def test_get_guide_returns_figure_signatures(client):
    r = client.get("/api/guides/labubu-forest-party")
    assert r.status_code == 200
    data = r.json()
    assert data["series_id"] == "labubu-forest-party"
    assert data["figure_signatures"], "seeded guide should have figure signatures"
    sig = data["figure_signatures"][0]
    assert "confidence_score" in sig
    assert 0 <= sig["confidence_score"] <= 100


def test_get_guide_for_series_without_guide_returns_placeholder(client):
    r = client.get("/api/guides/molly-space-travel")
    assert r.status_code == 200
    data = r.json()
    assert data["figure_signatures"] == []


def test_get_guide_unknown_series_404s(client):
    r = client.get("/api/guides/does-not-exist")
    assert r.status_code == 404


def test_add_contribution_and_reflect_in_guide(client):
    r = client.post(
        "/api/guides/labubu-forest-party/contributions",
        json={
            "figure_id": "lfp-pinecone-guard",
            "technique_type": "weight",
            "claim_text": "Measured 46g on a digital scale.",
            "weight_range_g": "46-48g",
        },
    )
    assert r.status_code == 201

    r2 = client.get("/api/guides/labubu-forest-party")
    pinecone = next(s for s in r2.json()["figure_signatures"] if s["figure_id"] == "lfp-pinecone-guard")
    assert pinecone["contribution_count"] >= 2  # seed already had 1


def test_add_contribution_rejects_unknown_technique(client):
    r = client.post(
        "/api/guides/labubu-forest-party/contributions",
        json={
            "figure_id": "lfp-pinecone-guard",
            "technique_type": "x-ray",
            "claim_text": "not a real technique",
        },
    )
    assert r.status_code == 422


def _auth_headers(client, email="voter1@example.com"):
    r = client.post("/api/auth/signup", json={"email": email, "password": "hunter2222"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _first_contribution_id(client):
    data = client.get("/api/guides/labubu-forest-party").json()
    return data["contributions"][0]["id"]


def test_vote_requires_auth(client):
    contribution_id = _first_contribution_id(client)
    r = client.post(f"/api/guides/contributions/{contribution_id}/vote", json={"direction": "up"})
    assert r.status_code == 401


def test_vote_up_increases_upvotes(client):
    contribution_id = _first_contribution_id(client)
    before = next(
        c for c in client.get("/api/guides/labubu-forest-party").json()["contributions"] if c["id"] == contribution_id
    )
    headers = _auth_headers(client, "voter2@example.com")
    r = client.post(f"/api/guides/contributions/{contribution_id}/vote", json={"direction": "up"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["upvotes"] == before["upvotes"] + 1


def test_changing_vote_does_not_double_count(client):
    contribution_id = _first_contribution_id(client)
    headers = _auth_headers(client, "voter3@example.com")
    up_result = client.post(
        f"/api/guides/contributions/{contribution_id}/vote", json={"direction": "up"}, headers=headers
    ).json()
    down_result = client.post(
        f"/api/guides/contributions/{contribution_id}/vote", json={"direction": "down"}, headers=headers
    ).json()
    # Switching this user's vote from up to down should move exactly one
    # vote, not add a second -- upvotes drops back down, downvotes rises by one.
    assert down_result["upvotes"] == up_result["upvotes"] - 1
    assert down_result["downvotes"] == up_result["downvotes"] + 1


def test_vote_rejects_invalid_direction(client):
    contribution_id = _first_contribution_id(client)
    headers = _auth_headers(client, "voter4@example.com")
    r = client.post(
        f"/api/guides/contributions/{contribution_id}/vote", json={"direction": "sideways"}, headers=headers
    )
    assert r.status_code == 422


def test_vote_unknown_contribution_422s(client):
    headers = _auth_headers(client, "voter5@example.com")
    r = client.post("/api/guides/contributions/999999/vote", json={"direction": "up"}, headers=headers)
    assert r.status_code == 422


def test_my_vote_reflected_in_guide_response(client):
    contribution_id = _first_contribution_id(client)
    headers = _auth_headers(client, "voter6@example.com")
    client.post(f"/api/guides/contributions/{contribution_id}/vote", json={"direction": "up"}, headers=headers)

    data = client.get("/api/guides/labubu-forest-party", headers=headers).json()
    mine = next(c for c in data["contributions"] if c["id"] == contribution_id)
    assert mine["my_vote"] == "up"

    # anonymous request to the same guide shouldn't see a my_vote
    anon_data = client.get("/api/guides/labubu-forest-party").json()
    anon_mine = next(c for c in anon_data["contributions"] if c["id"] == contribution_id)
    assert anon_mine["my_vote"] is None


def test_voting_raises_confidence_score(client):
    contribution_id = _first_contribution_id(client)
    figure_id = next(
        c["figure_id"] for c in client.get("/api/guides/labubu-forest-party").json()["contributions"]
        if c["id"] == contribution_id
    )
    before = next(
        s for s in client.get("/api/guides/labubu-forest-party").json()["figure_signatures"]
        if s["figure_id"] == figure_id
    )
    headers = _auth_headers(client, "voter7@example.com")
    client.post(f"/api/guides/contributions/{contribution_id}/vote", json={"direction": "up"}, headers=headers)

    after = next(
        s for s in client.get("/api/guides/labubu-forest-party").json()["figure_signatures"]
        if s["figure_id"] == figure_id
    )
    assert after["confidence_score"] >= before["confidence_score"]
