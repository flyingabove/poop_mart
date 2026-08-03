def test_index_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_version_endpoint(client):
    r = client.get("/api/version")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_endpoint(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
