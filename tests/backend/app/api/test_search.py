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


def test_search_tolerates_typo_in_brand_line(client):
    r = client.get("/api/search", params={"q": "skullpanada"})  # typo for "skullpanda"
    assert r.status_code == 200
    data = r.json()
    assert any(s["id"] == "skullpanda-city-of-night" for s in data["series"])


def test_search_tolerates_typo_in_series_name(client):
    r = client.get("/api/search", params={"q": "croybaby"})  # typo for "crybaby"
    assert r.status_code == 200
    data = r.json()
    assert any(s["id"] == "crybaby-crying-again" for s in data["series"])


def test_search_exact_substring_hit_not_duplicated_by_fuzzy(client):
    r = client.get("/api/search", params={"q": "labubu"})
    data = r.json()
    ids = [s["id"] for s in data["series"] if s["id"] == "labubu-forest-party"]
    assert len(ids) == 1  # substring match, not also re-added by the fuzzy pass


def test_search_unrelated_query_returns_nothing(client):
    r = client.get("/api/search", params={"q": "xyzxyzxyz-not-a-toy"})
    assert r.status_code == 200
    data = r.json()
    assert data["series"] == []
    assert data["figures"] == []
