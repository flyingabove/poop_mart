def test_search_matches_series_by_name(client):
    r = client.get("/api/search", params={"q": "labubu"})
    assert r.status_code == 200
    data = r.json()
    assert any(s["id"] == "labubu-forest-party" for s in data["series"])


def test_search_matches_alias(client):
    r = client.get("/api/search", params={"q": "forest party labubu"})
    assert r.status_code == 200
    data = r.json()
    assert any(s["id"] == "labubu-forest-party" for s in data["series"])


def test_search_requires_query(client):
    r = client.get("/api/search")
    assert r.status_code == 422
