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


def test_new_user_has_no_guide_contributor_or_top_reviewer_badge(client):
    signup = client.post("/api/auth/signup", json={"email": "nobadges@example.com", "password": "hunter22"})
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    badges = client.get("/api/auth/me", headers=headers).json()["badges"]
    codes = [b["code"] for b in badges]
    assert "guide_contributor" not in codes
    assert "top_reviewer" not in codes


def test_guide_contributor_badge_after_threshold_contributions(client):
    signup = client.post("/api/auth/signup", json={"email": "badge-contrib@example.com", "password": "hunter22"})
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    figures = ["lfp-forest-ranger", "lfp-berry-picker", "lfp-mushroom-nap"]
    for figure_id in figures:
        r = client.post(
            "/api/guides/labubu-forest-party/contributions",
            json={"figure_id": figure_id, "technique_type": "weight", "claim_text": "test contribution"},
            headers=headers,
        )
        assert r.status_code == 201

    badges = client.get("/api/auth/me", headers=headers).json()["badges"]
    contributor_badge = next((b for b in badges if b["code"] == "guide_contributor"), None)
    assert contributor_badge is not None
    assert contributor_badge["label"] == "Guide Contributor"


def test_no_guide_contributor_badge_below_threshold(client):
    signup = client.post("/api/auth/signup", json={"email": "badge-under@example.com", "password": "hunter22"})
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    client.post(
        "/api/guides/labubu-forest-party/contributions",
        json={"figure_id": "lfp-forest-ranger", "technique_type": "weight", "claim_text": "just one"},
        headers=headers,
    )

    badges = client.get("/api/auth/me", headers=headers).json()["badges"]
    assert not any(b["code"] == "guide_contributor" for b in badges)


def test_top_reviewer_badge_after_threshold_reviews(client):
    signup = client.post("/api/auth/signup", json={"email": "badge-reviewer@example.com", "password": "hunter22"})
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    # Figures NOT used by test_reviews.py's exact-count assertions -- this
    # suite shares a DB across the whole session, and cb-tears/
    # lfp-forest-ranger/lm-vanilla/sp-nightwatch all have review_count == N
    # assertions elsewhere that an extra review here would silently break.
    for figure_id in ["lfp-berry-picker", "lfp-mushroom-nap", "lfp-firefly-watcher"]:
        r = client.post(f"/api/figures/{figure_id}/reviews", json={"rating": 4}, headers=headers)
        assert r.status_code == 201

    badges = client.get("/api/auth/me", headers=headers).json()["badges"]
    assert any(b["code"] == "top_reviewer" for b in badges)


def test_login_rate_limited_after_too_many_failed_attempts(client):
    client.post("/api/auth/signup", json={"email": "ratelimit1@example.com", "password": "hunter22"})
    for _ in range(5):
        r = client.post("/api/auth/login", json={"email": "ratelimit1@example.com", "password": "wrong-pw"})
        assert r.status_code == 401

    r = client.post("/api/auth/login", json={"email": "ratelimit1@example.com", "password": "wrong-pw"})
    assert r.status_code == 429

    # even the *correct* password is now blocked -- the limiter caps
    # attempts, it doesn't just reject bad guesses
    r2 = client.post("/api/auth/login", json={"email": "ratelimit1@example.com", "password": "hunter22"})
    assert r2.status_code == 429


def test_successful_login_resets_rate_limit(client):
    client.post("/api/auth/signup", json={"email": "ratelimit2@example.com", "password": "hunter22"})
    for _ in range(4):
        client.post("/api/auth/login", json={"email": "ratelimit2@example.com", "password": "wrong-pw"})

    r = client.post("/api/auth/login", json={"email": "ratelimit2@example.com", "password": "hunter22"})
    assert r.status_code == 200  # 5th attempt, still within the limit, and correct

    # counter reset on success -> another login right away isn't blocked
    r2 = client.post("/api/auth/login", json={"email": "ratelimit2@example.com", "password": "hunter22"})
    assert r2.status_code == 200


def test_login_rate_limit_is_per_ip_even_across_different_emails(client, monkeypatch):
    from backend.app.api import auth as auth_module

    client.post("/api/auth/signup", json={"email": "ratelimit3a@example.com", "password": "hunter22"})
    client.post("/api/auth/signup", json={"email": "ratelimit3b@example.com", "password": "hunter22"})

    monkeypatch.setattr(auth_module, "_client_ip", lambda request: "1.2.3.4")
    for _ in range(5):
        client.post("/api/auth/login", json={"email": "ratelimit3a@example.com", "password": "wrong-pw"})

    # same simulated IP, a *different* account -- still blocked, because
    # the IP-level cap (not just the email-level one) is exhausted too
    r = client.post("/api/auth/login", json={"email": "ratelimit3b@example.com", "password": "hunter22"})
    assert r.status_code == 429

    # a genuinely different source IP for that second account isn't
    # affected by the first IP's exhausted attempts -- proves the email
    # key and IP key are tracked independently, not conflated
    monkeypatch.setattr(auth_module, "_client_ip", lambda request: "5.6.7.8")
    r2 = client.post("/api/auth/login", json={"email": "ratelimit3b@example.com", "password": "hunter22"})
    assert r2.status_code == 200


def test_signup_rate_limited_after_too_many_attempts(client):
    for i in range(10):
        r = client.post("/api/auth/signup", json={"email": f"burst{i}@example.com", "password": "hunter22"})
        assert r.status_code == 201

    r = client.post("/api/auth/signup", json={"email": "burst-over-limit@example.com", "password": "hunter22"})
    assert r.status_code == 429
