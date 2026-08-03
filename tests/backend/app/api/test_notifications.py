from backend.app.notifications.service import notify_followers_of_new_card


def _auth_headers(client, email="notif1@example.com"):
    r = client.post("/api/auth/signup", json={"email": email, "password": "hunter2222"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_notifications_empty_for_new_user(client):
    headers = _auth_headers(client)
    r = client.get("/api/notifications", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["unread_count"] == 0
    assert data["notifications"] == []


def test_notifications_requires_auth(client):
    assert client.get("/api/notifications").status_code == 401


def test_follow_then_new_card_creates_notification(client):
    headers = _auth_headers(client, "notif2@example.com")
    client.post("/api/follows/series/labubu-forest-party", headers=headers)

    # Other tests in this shared-DB suite may also follow this series, so
    # only assert this specific user received a notification, not an exact
    # global count (which depends on test execution order elsewhere).
    count = notify_followers_of_new_card("test-card-1", "labubu-forest-party", "Test headline")
    assert count >= 1

    data = client.get("/api/notifications", headers=headers).json()
    assert data["unread_count"] == 1
    assert data["notifications"][0]["body"] == "Test headline"
    assert data["notifications"][0]["notification_type"] == "followed_series_update"


def test_notify_no_followers_is_noop(client):
    count = notify_followers_of_new_card("test-card-2", "dimoo-world-travel", "Nobody follows this")
    assert count == 0


def test_notify_without_series_id_is_noop(client):
    count = notify_followers_of_new_card("test-card-3", None, "No series")
    assert count == 0


def test_mark_notification_read(client):
    headers = _auth_headers(client, "notif3@example.com")
    client.post("/api/follows/series/labubu-forest-party", headers=headers)
    notify_followers_of_new_card("test-card-4", "labubu-forest-party", "Another headline")

    notif_id = client.get("/api/notifications", headers=headers).json()["notifications"][0]["id"]
    r = client.post(f"/api/notifications/{notif_id}/read", headers=headers)
    assert r.status_code == 200

    assert client.get("/api/notifications", headers=headers).json()["unread_count"] == 0


def test_mark_already_read_404s(client):
    headers = _auth_headers(client, "notif5@example.com")
    client.post("/api/follows/series/labubu-forest-party", headers=headers)
    notify_followers_of_new_card("test-card-7", "labubu-forest-party", "Once")
    notif_id = client.get("/api/notifications", headers=headers).json()["notifications"][0]["id"]

    client.post(f"/api/notifications/{notif_id}/read", headers=headers)
    r = client.post(f"/api/notifications/{notif_id}/read", headers=headers)
    assert r.status_code == 404


def test_unread_only_filter(client):
    headers = _auth_headers(client, "notif4@example.com")
    client.post("/api/follows/series/labubu-forest-party", headers=headers)
    notify_followers_of_new_card("test-card-5", "labubu-forest-party", "First")
    notify_followers_of_new_card("test-card-6", "labubu-forest-party", "Second")

    notif_id = client.get("/api/notifications", headers=headers).json()["notifications"][0]["id"]
    client.post(f"/api/notifications/{notif_id}/read", headers=headers)

    unread = client.get("/api/notifications", params={"unread_only": True}, headers=headers).json()
    assert len(unread["notifications"]) == 1
