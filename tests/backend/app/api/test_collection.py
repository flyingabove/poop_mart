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


def test_editing_condition_updates_not_duplicates(client):
    # USER_PROFILES_AND_SOCIAL_DESIGN.md documents condition as a
    # first-class CollectionItem field; posting again for the same figure
    # is how it's edited (upsert), not a second entry.
    headers = _auth_headers(client, "collector6@example.com")
    client.post("/api/collection", json={"figure_id": "lfp-forest-ranger", "condition": "sealed"}, headers=headers)
    client.post("/api/collection", json={"figure_id": "lfp-forest-ranger", "condition": "opened"}, headers=headers)

    items = client.get("/api/collection", headers=headers).json()["items"]
    matching = [i for i in items if i["figure_id"] == "lfp-forest-ranger"]
    assert len(matching) == 1
    assert matching[0]["condition"] == "opened"


def test_add_with_explicit_acquired_at(client):
    # DATA_MODEL_INVENTORY.md documents acquired_at as a first-class
    # CollectionItem field -- letting a client provide it (rather than
    # always defaulting to "now") matters for anyone backfilling a
    # collection they already owned before using the app.
    headers = _auth_headers(client, "collector7@example.com")
    past_timestamp = 1700000000  # 2023-11-14, clearly not "now"
    client.post(
        "/api/collection",
        json={"figure_id": "lfp-forest-ranger", "acquired_at": past_timestamp},
        headers=headers,
    )

    items = client.get("/api/collection", headers=headers).json()["items"]
    item = next(i for i in items if i["figure_id"] == "lfp-forest-ranger")
    assert item["acquired_at"] == past_timestamp


def test_editing_condition_preserves_acquired_at(client):
    # Regression guard: a condition-only edit (acquired_at omitted) must
    # NOT silently reset the item's acquisition date to today -- that
    # would corrupt real collection history for every existing item the
    # moment its condition is ever edited.
    headers = _auth_headers(client, "collector8@example.com")
    past_timestamp = 1650000000  # 2022-04-15
    client.post(
        "/api/collection",
        json={"figure_id": "lfp-forest-ranger", "acquired_at": past_timestamp},
        headers=headers,
    )
    client.post(
        "/api/collection",
        json={"figure_id": "lfp-forest-ranger", "condition": "displayed"},
        headers=headers,
    )

    items = client.get("/api/collection", headers=headers).json()["items"]
    item = next(i for i in items if i["figure_id"] == "lfp-forest-ranger")
    assert item["condition"] == "displayed"
    assert item["acquired_at"] == past_timestamp


def test_editing_acquired_at_updates_it(client):
    headers = _auth_headers(client, "collector9@example.com")
    client.post(
        "/api/collection",
        json={"figure_id": "lfp-forest-ranger", "acquired_at": 1600000000},
        headers=headers,
    )
    client.post(
        "/api/collection",
        json={"figure_id": "lfp-forest-ranger", "acquired_at": 1650000000},
        headers=headers,
    )

    items = client.get("/api/collection", headers=headers).json()["items"]
    item = next(i for i in items if i["figure_id"] == "lfp-forest-ranger")
    assert item["acquired_at"] == 1650000000


def test_editing_photo_url_preserves_condition_and_acquired_at(client):
    # photo_url is the last of the CollectionItem fields
    # USER_PROFILES_AND_SOCIAL_DESIGN.md documents ("optional photo") --
    # accepting a plain external link needs no upload infrastructure,
    # same reasoning already applied to guide contributions' video_url.
    # This mirrors the exact payload the frontend's edit-photo flow sends
    # (condition preserved, photo_url set, acquired_at omitted) and
    # checks nothing else gets silently clobbered along the way.
    headers = _auth_headers(client, "collector10@example.com")
    past_timestamp = 1620000000
    client.post(
        "/api/collection",
        json={"figure_id": "lfp-forest-ranger", "condition": "sealed", "acquired_at": past_timestamp},
        headers=headers,
    )
    client.post(
        "/api/collection",
        json={
            "figure_id": "lfp-forest-ranger",
            "condition": "sealed",
            "photo_url": "https://example.com/my-figure.jpg",
        },
        headers=headers,
    )

    items = client.get("/api/collection", headers=headers).json()["items"]
    item = next(i for i in items if i["figure_id"] == "lfp-forest-ranger")
    assert item["photo_url"] == "https://example.com/my-figure.jpg"
    assert item["condition"] == "sealed"
    assert item["acquired_at"] == past_timestamp
