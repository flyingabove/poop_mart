def test_feed_returns_seeded_cards(client):
    r = client.get("/api/feed")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] > 0
    assert data["cards"], "seed data should produce at least one feed card"
    card = data["cards"][0]
    assert set(["id", "card_type", "title", "body", "created_at"]) <= card.keys()


def test_feed_filters_by_card_type(client):
    r = client.get("/api/feed", params={"card_type": "shake_guide"})
    assert r.status_code == 200
    data = r.json()
    assert all(c["card_type"] == "shake_guide" for c in data["cards"])
    assert data["count"] >= 1


def test_feed_guides_tab_only_returns_shake_guide_cards(client):
    r = client.get("/api/feed", params={"tab": "guides"})
    assert r.status_code == 200
    data = r.json()
    assert all(c["card_type"] == "shake_guide" for c in data["cards"])


def test_anonymous_for_you_is_not_personalized(client):
    r = client.get("/api/feed", params={"tab": "for_you"})
    assert r.status_code == 200
    assert r.json()["personalized"] is False


def test_for_you_is_personalized_after_following_a_series(client):
    signup = client.post(
        "/api/auth/signup", json={"email": "feed-personalize@example.com", "password": "hunter2222"}
    )
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    client.post("/api/follows/series/crybaby-crying-again", headers=headers)

    r = client.get("/api/feed", params={"tab": "for_you"}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["personalized"] is True

    followed_cards = [c for c in data["cards"] if c["series_id"] == "crybaby-crying-again"]
    assert followed_cards, "seed data should include at least one crybaby-crying-again card"
    assert all(c["followed"] is True for c in followed_cards)
    assert any(c.get("followed") is False for c in data["cards"]), "unfollowed cards should still appear, just unboosted"


def _auth_headers(client, email="poster1@example.com"):
    r = client.post("/api/auth/signup", json={"email": email, "password": "hunter2222"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_seeded_cards_have_no_poster(client):
    data = client.get("/api/feed").json()
    assert any(c["poster"] is None for c in data["cards"])


def test_create_community_post_requires_auth(client):
    r = client.post(
        "/api/feed/posts",
        json={"figure_id": "lfp-forest-ranger", "title": "Pulled it!", "body": "So excited"},
    )
    assert r.status_code == 401


def test_create_community_post_appears_in_feed_with_poster(client):
    headers = _auth_headers(client, "poster2@example.com")
    r = client.post(
        "/api/feed/posts",
        json={"figure_id": "lfp-berry-picker", "title": "Finally got Berry Picker!", "body": "Third box's the charm"},
        headers=headers,
    )
    assert r.status_code == 201
    post_id = r.json()["id"]
    assert r.json()["series_id"] == "labubu-forest-party"  # auto-derived from the figure

    data = client.get("/api/feed", params={"card_type": "community_post"}).json()
    mine = next(c for c in data["cards"] if c["id"] == post_id)
    assert mine["title"] == "Finally got Berry Picker!"
    assert mine["poster"] == "poster2"
    assert mine["figure_id"] == "lfp-berry-picker"
    assert mine["poster_id"], "poster_id must be exposed so the post's author can be followed"


def test_create_community_post_unknown_figure_422s(client):
    headers = _auth_headers(client, "poster3@example.com")
    r = client.post(
        "/api/feed/posts",
        json={"figure_id": "does-not-exist", "title": "x", "body": "y"},
        headers=headers,
    )
    assert r.status_code == 422


def test_create_community_post_rejects_empty_title(client):
    headers = _auth_headers(client, "poster4@example.com")
    r = client.post(
        "/api/feed/posts",
        json={"figure_id": "lfp-forest-ranger", "title": "  ", "body": "some body"},
        headers=headers,
    )
    assert r.status_code == 422


def test_community_post_participates_in_personalization(client):
    headers = _auth_headers(client, "poster5@example.com")
    client.post("/api/follows/series/labubu-forest-party", headers=headers)
    r = client.post(
        "/api/feed/posts",
        json={"figure_id": "lfp-mushroom-nap", "title": "Got Mushroom Nap", "body": "Love it"},
        headers=headers,
    )
    post_id = r.json()["id"]

    data = client.get("/api/feed", params={"tab": "for_you"}, headers=headers).json()
    mine = next(c for c in data["cards"] if c["id"] == post_id)
    assert mine["followed"] is True


def test_delete_own_community_post(client):
    headers = _auth_headers(client, "poster6@example.com")
    post_id = client.post(
        "/api/feed/posts",
        json={"figure_id": "lfp-forest-ranger", "title": "To be deleted", "body": "bye"},
        headers=headers,
    ).json()["id"]

    r = client.delete(f"/api/feed/posts/{post_id}", headers=headers)
    assert r.status_code == 200

    data = client.get("/api/feed", params={"card_type": "community_post"}).json()
    assert not any(c["id"] == post_id for c in data["cards"])


def test_delete_community_post_requires_auth(client):
    headers = _auth_headers(client, "poster7@example.com")
    post_id = client.post(
        "/api/feed/posts",
        json={"figure_id": "lfp-forest-ranger", "title": "No auth delete", "body": "x"},
        headers=headers,
    ).json()["id"]

    r = client.delete(f"/api/feed/posts/{post_id}")
    assert r.status_code == 401


def test_cannot_delete_other_users_post(client):
    headers_a = _auth_headers(client, "poster8a@example.com")
    headers_b = _auth_headers(client, "poster8b@example.com")
    post_id = client.post(
        "/api/feed/posts",
        json={"figure_id": "lfp-forest-ranger", "title": "A's post", "body": "mine"},
        headers=headers_a,
    ).json()["id"]

    r = client.delete(f"/api/feed/posts/{post_id}", headers=headers_b)
    assert r.status_code == 404

    data = client.get("/api/feed", params={"card_type": "community_post"}).json()
    assert any(c["id"] == post_id for c in data["cards"])


def test_delete_unknown_post_404s(client):
    headers = _auth_headers(client, "poster9@example.com")
    r = client.delete("/api/feed/posts/post:does-not-exist", headers=headers)
    assert r.status_code == 404
