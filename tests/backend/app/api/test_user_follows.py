def _signup(client, email):
    r = client.post("/api/auth/signup", json={"email": email, "password": "hunter2222"})
    data = r.json()
    return data["user_id"], {"Authorization": f"Bearer {data['access_token']}"}


def test_follow_and_list_user(client):
    a_id, a_headers = _signup(client, "userfollow-a@example.com")
    b_id, b_headers = _signup(client, "userfollow-b@example.com")

    r = client.post(f"/api/follows/users/{b_id}", headers=a_headers)
    assert r.status_code == 201

    followed = client.get("/api/follows/users", headers=a_headers).json()["users"]
    assert any(u["user_id"] == b_id and u["handle"] == "userfollow-b" for u in followed)


def test_follow_user_requires_auth(client):
    _id, _headers = _signup(client, "userfollow-c@example.com")
    r = client.post(f"/api/follows/users/{_id}")
    assert r.status_code == 401


def test_cannot_follow_self(client):
    my_id, headers = _signup(client, "userfollow-d@example.com")
    r = client.post(f"/api/follows/users/{my_id}", headers=headers)
    assert r.status_code == 422


def test_follow_unknown_user_404s(client):
    _id, headers = _signup(client, "userfollow-e@example.com")
    r = client.post("/api/follows/users/does-not-exist", headers=headers)
    assert r.status_code == 404


def test_follow_is_idempotent(client):
    _a_id, a_headers = _signup(client, "userfollow-f@example.com")
    b_id, _b_headers = _signup(client, "userfollow-g@example.com")

    assert client.post(f"/api/follows/users/{b_id}", headers=a_headers).status_code == 201
    assert client.post(f"/api/follows/users/{b_id}", headers=a_headers).status_code == 201

    followed = client.get("/api/follows/users", headers=a_headers).json()["users"]
    assert len([u for u in followed if u["user_id"] == b_id]) == 1


def test_unfollow_user(client):
    _a_id, a_headers = _signup(client, "userfollow-h@example.com")
    b_id, _b_headers = _signup(client, "userfollow-i@example.com")
    client.post(f"/api/follows/users/{b_id}", headers=a_headers)

    r = client.delete(f"/api/follows/users/{b_id}", headers=a_headers)
    assert r.status_code == 200

    followed = client.get("/api/follows/users", headers=a_headers).json()["users"]
    assert not any(u["user_id"] == b_id for u in followed)


def test_unfollow_not_following_404s(client):
    _a_id, a_headers = _signup(client, "userfollow-j@example.com")
    b_id, _b_headers = _signup(client, "userfollow-k@example.com")
    r = client.delete(f"/api/follows/users/{b_id}", headers=a_headers)
    assert r.status_code == 404


def test_ranking_owner_id_supports_follow_flow(client):
    """End-to-end: create a ranking, follow its owner via the id the
    ranking detail endpoint exposes -- proves the two features actually
    connect, not just that each works in isolation."""
    owner_id, owner_headers = _signup(client, "rankingowner@example.com")
    _, follower_headers = _signup(client, "rankingfollower@example.com")

    ranking = client.post("/api/rankings", json={"title": "Followable"}, headers=owner_headers).json()
    detail = client.get(f"/api/rankings/{ranking['id']}").json()
    assert detail["owner_id"] == owner_id

    r = client.post(f"/api/follows/users/{detail['owner_id']}", headers=follower_headers)
    assert r.status_code == 201
