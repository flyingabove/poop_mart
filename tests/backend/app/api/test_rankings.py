def _auth_headers(client, email="ranker1@example.com"):
    r = client.post("/api/auth/signup", json={"email": email, "password": "hunter2222"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_create_and_list_ranking(client):
    headers = _auth_headers(client, "ranker2@example.com")
    r = client.post("/api/rankings", json={"title": "My Top Labubu Colorways"}, headers=headers)
    assert r.status_code == 201
    assert r.json()["title"] == "My Top Labubu Colorways"

    rankings = client.get("/api/rankings", headers=headers).json()["rankings"]
    assert any(rk["title"] == "My Top Labubu Colorways" for rk in rankings)


def test_create_ranking_requires_auth(client):
    r = client.post("/api/rankings", json={"title": "No auth"})
    assert r.status_code == 401


def test_create_ranking_rejects_empty_title(client):
    headers = _auth_headers(client, "ranker3@example.com")
    r = client.post("/api/rankings", json={"title": "   "}, headers=headers)
    assert r.status_code == 422


def test_rankings_are_isolated_per_user(client):
    headers_a = _auth_headers(client, "ranker-a@example.com")
    headers_b = _auth_headers(client, "ranker-b@example.com")
    client.post("/api/rankings", json={"title": "A's ranking"}, headers=headers_a)

    rankings_b = client.get("/api/rankings", headers=headers_b).json()["rankings"]
    assert not any(rk["title"] == "A's ranking" for rk in rankings_b)


def test_get_ranking_detail_is_public(client):
    headers = _auth_headers(client, "ranker4@example.com")
    created = client.post("/api/rankings", json={"title": "Public list"}, headers=headers).json()

    # no auth headers on this GET -- viewing a ranking is public
    r = client.get(f"/api/rankings/{created['id']}")
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Public list"
    assert data["owner"] == "ranker4"
    assert data["items"] == []


def test_get_unknown_ranking_404s(client):
    r = client.get("/api/rankings/999999")
    assert r.status_code == 404


def test_add_and_remove_ranking_item(client):
    headers = _auth_headers(client, "ranker5@example.com")
    created = client.post("/api/rankings", json={"title": "With items"}, headers=headers).json()
    ranking_id = created["id"]

    r = client.post(f"/api/rankings/{ranking_id}/items", json={"figure_id": "lfp-forest-ranger"}, headers=headers)
    assert r.status_code == 201

    detail = client.get(f"/api/rankings/{ranking_id}").json()
    assert len(detail["items"]) == 1
    assert detail["items"][0]["figure_id"] == "lfp-forest-ranger"
    assert detail["items"][0]["figure_name"] == "Forest Ranger"

    r2 = client.delete(f"/api/rankings/{ranking_id}/items/lfp-forest-ranger", headers=headers)
    assert r2.status_code == 200

    detail2 = client.get(f"/api/rankings/{ranking_id}").json()
    assert detail2["items"] == []


def test_add_item_preserves_insertion_order(client):
    headers = _auth_headers(client, "ranker6@example.com")
    created = client.post("/api/rankings", json={"title": "Ordered"}, headers=headers).json()
    ranking_id = created["id"]

    for figure_id in ["lfp-mushroom-nap", "lfp-forest-ranger", "lfp-berry-picker"]:
        client.post(f"/api/rankings/{ranking_id}/items", json={"figure_id": figure_id}, headers=headers)

    detail = client.get(f"/api/rankings/{ranking_id}").json()
    figure_ids = [i["figure_id"] for i in detail["items"]]
    assert figure_ids == ["lfp-mushroom-nap", "lfp-forest-ranger", "lfp-berry-picker"]


def test_add_item_unknown_figure_404s(client):
    headers = _auth_headers(client, "ranker7@example.com")
    created = client.post("/api/rankings", json={"title": "Bad figure"}, headers=headers).json()
    r = client.post(f"/api/rankings/{created['id']}/items", json={"figure_id": "does-not-exist"}, headers=headers)
    assert r.status_code == 404


def test_add_item_to_other_users_ranking_404s(client):
    headers_a = _auth_headers(client, "ranker8a@example.com")
    headers_b = _auth_headers(client, "ranker8b@example.com")
    created = client.post("/api/rankings", json={"title": "A's list"}, headers=headers_a).json()

    r = client.post(
        f"/api/rankings/{created['id']}/items", json={"figure_id": "lfp-forest-ranger"}, headers=headers_b
    )
    assert r.status_code == 404  # doesn't leak whether the ranking exists for another user


def test_delete_ranking(client):
    headers = _auth_headers(client, "ranker9@example.com")
    created = client.post("/api/rankings", json={"title": "To delete"}, headers=headers).json()

    r = client.delete(f"/api/rankings/{created['id']}", headers=headers)
    assert r.status_code == 200

    r2 = client.get(f"/api/rankings/{created['id']}")
    assert r2.status_code == 404


def test_delete_other_users_ranking_404s(client):
    headers_a = _auth_headers(client, "ranker10a@example.com")
    headers_b = _auth_headers(client, "ranker10b@example.com")
    created = client.post("/api/rankings", json={"title": "A's list 2"}, headers=headers_a).json()

    r = client.delete(f"/api/rankings/{created['id']}", headers=headers_b)
    assert r.status_code == 404

    # still there for the actual owner
    assert client.get(f"/api/rankings/{created['id']}").status_code == 200


def test_adding_same_figure_twice_does_not_duplicate(client):
    headers = _auth_headers(client, "ranker11@example.com")
    created = client.post("/api/rankings", json={"title": "No dupes"}, headers=headers).json()
    ranking_id = created["id"]

    client.post(f"/api/rankings/{ranking_id}/items", json={"figure_id": "lfp-forest-ranger"}, headers=headers)
    client.post(f"/api/rankings/{ranking_id}/items", json={"figure_id": "lfp-forest-ranger"}, headers=headers)

    detail = client.get(f"/api/rankings/{ranking_id}").json()
    assert len(detail["items"]) == 1
