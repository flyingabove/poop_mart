def test_price_history_for_seeded_figure(client):
    r = client.get("/api/figures/lfp-moonlit-wanderer/price-history")
    assert r.status_code == 200
    data = r.json()
    assert len(data["history"]) >= 2
    # seeded as a rising trend
    assert data["history"][-1]["median_price"] > data["history"][0]["median_price"]


def test_price_history_unknown_figure_404s(client):
    r = client.get("/api/figures/does-not-exist/price-history")
    assert r.status_code == 404


def test_figure_detail_includes_current_price(client):
    r = client.get("/api/figures/lfp-moonlit-wanderer")
    assert r.status_code == 200
    data = r.json()
    assert data["figure"]["id"] == "lfp-moonlit-wanderer"
    assert data["current_price"]["median_price"] > 0
