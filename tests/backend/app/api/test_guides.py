def test_get_guide_returns_figure_signatures(client):
    r = client.get("/api/guides/labubu-forest-party")
    assert r.status_code == 200
    data = r.json()
    assert data["series_id"] == "labubu-forest-party"
    assert data["figure_signatures"], "seeded guide should have figure signatures"
    sig = data["figure_signatures"][0]
    assert "confidence_score" in sig
    assert 0 <= sig["confidence_score"] <= 100


def test_get_guide_for_series_without_guide_returns_placeholder(client):
    r = client.get("/api/guides/molly-space-travel")
    assert r.status_code == 200
    data = r.json()
    assert data["figure_signatures"] == []


def test_get_guide_unknown_series_404s(client):
    r = client.get("/api/guides/does-not-exist")
    assert r.status_code == 404


def test_add_contribution_and_reflect_in_guide(client):
    r = client.post(
        "/api/guides/labubu-forest-party/contributions",
        json={
            "figure_id": "lfp-pinecone-guard",
            "technique_type": "weight",
            "claim_text": "Measured 46g on a digital scale.",
            "weight_range_g": "46-48g",
        },
    )
    assert r.status_code == 201

    r2 = client.get("/api/guides/labubu-forest-party")
    pinecone = next(s for s in r2.json()["figure_signatures"] if s["figure_id"] == "lfp-pinecone-guard")
    assert pinecone["contribution_count"] >= 2  # seed already had 1


def test_add_contribution_rejects_unknown_technique(client):
    r = client.post(
        "/api/guides/labubu-forest-party/contributions",
        json={
            "figure_id": "lfp-pinecone-guard",
            "technique_type": "x-ray",
            "claim_text": "not a real technique",
        },
    )
    assert r.status_code == 422
