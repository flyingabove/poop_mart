def _auth_headers(client, email="collector1@example.com"):
    r = client.post("/api/auth/signup", json={"email": email, "password": "hunter2222"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_add_and_list_collection_item(client):
    headers = _auth_headers(client)
    r = client.post(
        "/api/collection", json={"figure_id": "lfp-forest-ranger", "condition": "mint"}, headers=headers
    )
    assert r.status_code == 201

    items = client.get("/api/collection", headers=headers).json()["items"]
    item = next(i for i in items if i["figure_id"] == "lfp-forest-ranger")
    assert item["condition"] == "mint"
    assert item["figure_name"] == "Forest Ranger"


def test_add_unknown_figure_404s(client):
    headers = _auth_headers(client, "collector2@example.com")
    r = client.post("/api/collection", json={"figure_id": "does-not-exist"}, headers=headers)
    assert r.status_code == 404


def test_collection_requires_auth(client):
    assert client.get("/api/collection").status_code == 401
    assert client.post("/api/collection", json={"figure_id": "lfp-forest-ranger"}).status_code == 401


def test_remove_collection_item(client):
    headers = _auth_headers(client, "collector3@example.com")
    client.post("/api/collection", json={"figure_id": "lfp-forest-ranger"}, headers=headers)

    r = client.delete("/api/collection/lfp-forest-ranger", headers=headers)
    assert r.status_code == 200

    items = client.get("/api/collection", headers=headers).json()["items"]
    assert not any(i["figure_id"] == "lfp-forest-ranger" for i in items)


def test_remove_missing_item_404s(client):
    headers = _auth_headers(client, "collector5@example.com")
    r = client.delete("/api/collection/lfp-forest-ranger", headers=headers)
    assert r.status_code == 404


def test_valuation_sums_priced_items(client):
    headers = _auth_headers(client, "collector4@example.com")
    client.post("/api/collection", json={"figure_id": "lfp-moonlit-wanderer"}, headers=headers)

    data = client.get("/api/collection/valuation", headers=headers).json()
    assert data["figure_count"] == 1
    assert data["priced_figure_count"] == 1
    assert data["total_value"] > 0


def test_collections_are_isolated_per_user(client):
    headers_a = _auth_headers(client, "isolated-a@example.com")
    headers_b = _auth_headers(client, "isolated-b@example.com")
    client.post("/api/collection", json={"figure_id": "lfp-forest-ranger"}, headers=headers_a)

    items_b = client.get("/api/collection", headers=headers_b).json()["items"]
    assert items_b == []
