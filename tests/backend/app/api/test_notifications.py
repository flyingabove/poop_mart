from backend.app.notifications.service import notify_followers_of_new_card


def _auth_headers(client, email="notif1@example.com"):
    r = client.post("/api/auth/signup", json={"email": email, "password": "hunter2222"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _signup(client, email):
    r = client.post("/api/auth/signup", json={"email": email, "password": "hunter2222"})
    data = r.json()
    return data["user_id"], {"Authorization": f"Bearer {data['access_token']}"}


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


def test_follow_user_then_post_creates_notification(client):
    b_id, b_headers = _signup(client, "notif-poster-a@example.com")
    _a_id, a_headers = _signup(client, "notif-follower-a@example.com")
    client.post(f"/api/follows/users/{b_id}", headers=a_headers)

    r = client.post(
        "/api/feed/posts",
        json={"figure_id": "lfp-forest-ranger", "title": "Notif test pull", "body": "hi"},
        headers=b_headers,
    )
    assert r.status_code == 201

    data = client.get("/api/notifications", headers=a_headers).json()
    notif = next(n for n in data["notifications"] if n["body"] == "Notif test pull")
    assert notif["notification_type"] == "followed_user_post"
    assert notif["title"] == "@notif-poster-a shared a new pull"
    assert notif["figure_id"] == "lfp-forest-ranger"
    assert notif["series_id"] == "labubu-forest-party"


def test_post_notification_not_sent_to_non_followers(client):
    _b_id, b_headers = _signup(client, "notif-poster-b@example.com")
    _c_id, c_headers = _signup(client, "notif-nonfollower-b@example.com")

    client.post(
        "/api/feed/posts",
        json={"figure_id": "lfp-forest-ranger", "title": "Not for you", "body": "hi"},
        headers=b_headers,
    )

    data = client.get("/api/notifications", headers=c_headers).json()
    assert not any(n["body"] == "Not for you" for n in data["notifications"])


def test_post_by_user_with_no_followers_is_noop(client):
    _id, headers = _signup(client, "notif-lonely-poster@example.com")
    r = client.post(
        "/api/feed/posts",
        json={"figure_id": "lfp-forest-ranger", "title": "Solo pull", "body": "hi"},
        headers=headers,
    )
    assert r.status_code == 201
    # the poster shouldn't notify themselves
    data = client.get("/api/notifications", headers=headers).json()
    assert not any(n["body"] == "Solo pull" for n in data["notifications"])
