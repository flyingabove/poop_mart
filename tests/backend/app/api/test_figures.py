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
