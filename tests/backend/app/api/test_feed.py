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
