def _auth_headers(client, email="follower1@example.com"):
    r = client.post("/api/auth/signup", json={"email": email, "password": "hunter2222"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_follow_and_list_series(client):
    headers = _auth_headers(client)
    r = client.post("/api/follows/series/labubu-forest-party", headers=headers)
    assert r.status_code == 201

    series = client.get("/api/follows/series", headers=headers).json()["series"]
    assert any(s["series_id"] == "labubu-forest-party" for s in series)


def test_follow_unknown_series_404s(client):
    headers = _auth_headers(client, "follower2@example.com")
    r = client.post("/api/follows/series/does-not-exist", headers=headers)
    assert r.status_code == 404


def test_follow_requires_auth(client):
    assert client.post("/api/follows/series/labubu-forest-party").status_code == 401


def test_follow_is_idempotent(client):
    headers = _auth_headers(client, "follower3@example.com")
    assert client.post("/api/follows/series/labubu-forest-party", headers=headers).status_code == 201
    # following again shouldn't error or duplicate
    assert client.post("/api/follows/series/labubu-forest-party", headers=headers).status_code == 201
    series = client.get("/api/follows/series", headers=headers).json()["series"]
    assert len([s for s in series if s["series_id"] == "labubu-forest-party"]) == 1


def test_unfollow_series(client):
    headers = _auth_headers(client, "follower4@example.com")
    client.post("/api/follows/series/labubu-forest-party", headers=headers)
    r = client.delete("/api/follows/series/labubu-forest-party", headers=headers)
    assert r.status_code == 200

    series = client.get("/api/follows/series", headers=headers).json()["series"]
    assert not any(s["series_id"] == "labubu-forest-party" for s in series)


def test_unfollow_not_following_404s(client):
    headers = _auth_headers(client, "follower5@example.com")
    r = client.delete("/api/follows/series/labubu-forest-party", headers=headers)
    assert r.status_code == 404
