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
    assert data["posts"] == []
    assert data["reviews"] == []
    assert data["guide_contributions"] == []


def _auth_headers(client, email):
    r = client.post("/api/auth/signup", json={"email": email, "password": "hunter2222"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_search_matches_community_post_title(client):
    headers = _auth_headers(client, "search-poster-a@example.com")
    client.post(
        "/api/feed/posts",
        json={"figure_id": "lfp-forest-ranger", "title": "Zzyzxquest99 unboxing", "body": "so happy"},
        headers=headers,
    )

    r = client.get("/api/search", params={"q": "zzyzxquest99"})
    assert r.status_code == 200
    hit = next(p for p in r.json()["posts"] if p["title"] == "Zzyzxquest99 unboxing")
    assert hit["figure_id"] == "lfp-forest-ranger"
    assert hit["figure_name"] == "Forest Ranger"
    assert hit["poster"] == "search-poster-a"


def test_search_matches_community_post_body(client):
    headers = _auth_headers(client, "search-poster-b@example.com")
    client.post(
        "/api/feed/posts",
        json={"figure_id": "lfp-forest-ranger", "title": "Another pull", "body": "found a Wobbleflarp42 today"},
        headers=headers,
    )

    r = client.get("/api/search", params={"q": "wobbleflarp42"})
    assert r.status_code == 200
    assert any(p["title"] == "Another pull" for p in r.json()["posts"])


def test_search_matches_review_text(client):
    headers = _auth_headers(client, "search-reviewer-a@example.com")
    client.post(
        "/api/figures/lfp-forest-ranger/reviews",
        json={"rating": 5, "text": "Smells faintly of Quixolatte99, love it"},
        headers=headers,
    )

    r = client.get("/api/search", params={"q": "quixolatte99"})
    assert r.status_code == 200
    hit = next(rv for rv in r.json()["reviews"] if rv["figure_id"] == "lfp-forest-ranger")
    assert hit["rating"] == 5
    assert hit["reviewer"] == "search-reviewer-a"
    assert hit["figure_name"] == "Forest Ranger"


def test_search_matches_guide_contribution_claim(client):
    headers = _auth_headers(client, "search-contributor-a@example.com")
    client.post(
        "/api/guides/labubu-forest-party/contributions",
        json={
            "figure_id": "lfp-forest-ranger",
            "technique_type": "sound",
            "claim_text": "Rattles like a Zibbertronic42 when shaken",
        },
        headers=headers,
    )

    r = client.get("/api/search", params={"q": "zibbertronic42"})
    assert r.status_code == 200
    hit = next(g for g in r.json()["guide_contributions"] if g["figure_id"] == "lfp-forest-ranger")
    assert hit["series_id"] == "labubu-forest-party"
    assert hit["technique_type"] == "sound"
    assert hit["contributor"] == "search-contributor-a"
