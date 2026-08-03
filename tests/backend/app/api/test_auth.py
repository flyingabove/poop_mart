def test_signup_creates_user_and_returns_token(client):
    r = client.post("/api/auth/signup", json={"email": "collector@example.com", "password": "hunter22"})
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == "collector@example.com"
    assert data["access_token"]


def test_signup_duplicate_email_rejected(client):
    body = {"email": "dupe@example.com", "password": "hunter22"}
    assert client.post("/api/auth/signup", json=body).status_code == 201
    r = client.post("/api/auth/signup", json=body)
    assert r.status_code == 422


def test_signup_short_password_rejected(client):
    r = client.post("/api/auth/signup", json={"email": "short@example.com", "password": "abc"})
    assert r.status_code == 422


def test_signup_invalid_email_rejected(client):
    r = client.post("/api/auth/signup", json={"email": "not-an-email", "password": "hunter22"})
    assert r.status_code == 422


def test_login_success(client):
    client.post("/api/auth/signup", json={"email": "login@example.com", "password": "hunter22"})
    r = client.post("/api/auth/login", json={"email": "login@example.com", "password": "hunter22"})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_wrong_password_rejected(client):
    client.post("/api/auth/signup", json={"email": "wrong@example.com", "password": "hunter22"})
    r = client.post("/api/auth/login", json={"email": "wrong@example.com", "password": "nope-nope"})
    assert r.status_code == 401


def test_login_unknown_email_rejected(client):
    r = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "hunter22"})
    assert r.status_code == 401


def test_me_requires_token(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_rejects_garbage_token(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


def test_me_with_valid_token(client):
    signup = client.post("/api/auth/signup", json={"email": "me@example.com", "password": "hunter22"})
    token = signup.json()["access_token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "me@example.com"
