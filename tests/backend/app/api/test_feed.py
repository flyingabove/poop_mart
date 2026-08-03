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
