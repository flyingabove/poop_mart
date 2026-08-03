def test_list_series_returns_all_series(client):
    r = client.get("/api/series")
    assert r.status_code == 200
    data = r.json()
    assert any(s["id"] == "labubu-forest-party" for s in data["series"])
    assert all("name" in s and "brand_line" in s for s in data["series"])


def test_get_series_detail_includes_figures(client):
    r = client.get("/api/series/labubu-forest-party")
    assert r.status_code == 200
    data = r.json()
    assert data["series"]["id"] == "labubu-forest-party"
    assert any(f["id"] == "lfp-forest-ranger" for f in data["figures"])


def test_get_unknown_series_404s(client):
    r = client.get("/api/series/does-not-exist")
    assert r.status_code == 404


def test_list_figures_returns_all_figures(client):
    r = client.get("/api/figures")
    assert r.status_code == 200
    data = r.json()
    assert any(f["id"] == "lfp-forest-ranger" for f in data["figures"])
    # figures from more than one series should be present in the unfiltered list
    series_ids = {f["series_id"] for f in data["figures"]}
    assert len(series_ids) > 1


def test_list_figures_filters_by_series_id(client):
    r = client.get("/api/figures", params={"series_id": "labubu-forest-party"})
    assert r.status_code == 200
    data = r.json()
    assert data["figures"]
    assert all(f["series_id"] == "labubu-forest-party" for f in data["figures"])


def test_get_unknown_figure_404s(client):
    r = client.get("/api/figures/does-not-exist")
    assert r.status_code == 404


def test_series_detail_includes_regions(client):
    # DATA_MODEL_INVENTORY.md documents Series.regions_available and
    # PRICE_TRACKING_DESIGN.md documents "regional availability" as a
    # real per-series field -- the seed data has always carried it, but
    # until now nothing in the frontend read it, and no test locked the
    # response shape in place.
    r = client.get("/api/series/labubu-forest-party")
    data = r.json()
    assert data["series"]["regions"] == "CN,US,KR,JP"


def test_figure_detail_includes_published_pull_rate(client):
    # DATA_MODEL_INVENTORY.md documents Figure.published_pull_rate.
    # lfp-moonlit-wanderer is the series' secret/chase figure, seeded
    # with a real 1/72 rate.
    r = client.get("/api/figures/lfp-moonlit-wanderer")
    data = r.json()
    assert data["figure"]["published_pull_rate"] == 1 / 72
