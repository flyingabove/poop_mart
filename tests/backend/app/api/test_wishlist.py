def _auth_headers(client, email="wisher1@example.com"):
    r = client.post("/api/auth/signup", json={"email": email, "password": "hunter2222"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_add_and_list_wishlist_item(client):
    headers = _auth_headers(client)
    r = client.post("/api/wishlist", json={"figure_id": "lm-pistachio", "alert_threshold": 100}, headers=headers)
    assert r.status_code == 201

    items = client.get("/api/wishlist", headers=headers).json()["items"]
    assert any(i["figure_id"] == "lm-pistachio" for i in items)


def test_wishlist_below_threshold_flag(client):
    headers = _auth_headers(client, "wisher2@example.com")
    # seeded lm-pistachio price trend ends at 49 (falling) -> a high threshold is already crossed
    client.post("/api/wishlist", json={"figure_id": "lm-pistachio", "alert_threshold": 1000}, headers=headers)

    items = client.get("/api/wishlist", headers=headers).json()["items"]
    item = next(i for i in items if i["figure_id"] == "lm-pistachio")
    assert item["below_threshold"] is True


def test_wishlist_above_threshold_not_flagged(client):
    headers = _auth_headers(client, "wisher-above@example.com")
    client.post("/api/wishlist", json={"figure_id": "lm-pistachio", "alert_threshold": 1}, headers=headers)

    items = client.get("/api/wishlist", headers=headers).json()["items"]
    item = next(i for i in items if i["figure_id"] == "lm-pistachio")
    assert item["below_threshold"] is False


def test_add_unknown_figure_404s(client):
    headers = _auth_headers(client, "wisher3@example.com")
    r = client.post("/api/wishlist", json={"figure_id": "does-not-exist"}, headers=headers)
    assert r.status_code == 404


def test_wishlist_requires_auth(client):
    assert client.get("/api/wishlist").status_code == 401


def test_remove_wishlist_item(client):
    headers = _auth_headers(client, "wisher4@example.com")
    client.post("/api/wishlist", json={"figure_id": "lm-pistachio"}, headers=headers)

    r = client.delete("/api/wishlist/lm-pistachio", headers=headers)
    assert r.status_code == 200

    items = client.get("/api/wishlist", headers=headers).json()["items"]
    assert items == []
