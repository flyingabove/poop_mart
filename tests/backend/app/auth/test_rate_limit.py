from backend.app.auth.rate_limit import RateLimiter


def test_allows_up_to_max_attempts():
    limiter = RateLimiter(max_attempts=3, window_seconds=60)
    assert limiter.check("k") is True
    assert limiter.check("k") is True
    assert limiter.check("k") is True


def test_blocks_after_max_attempts():
    limiter = RateLimiter(max_attempts=3, window_seconds=60)
    for _ in range(3):
        limiter.check("k")
    assert limiter.check("k") is False
    assert limiter.check("k") is False  # still blocked, doesn't reset itself


def test_keys_are_independent():
    limiter = RateLimiter(max_attempts=1, window_seconds=60)
    assert limiter.check("a") is True
    assert limiter.check("b") is True  # different key, unaffected by "a"
    assert limiter.check("a") is False


def test_reset_clears_the_key():
    limiter = RateLimiter(max_attempts=1, window_seconds=60)
    limiter.check("k")
    assert limiter.check("k") is False
    limiter.reset("k")
    assert limiter.check("k") is True


def test_window_expiry_allows_new_attempts(monkeypatch):
    limiter = RateLimiter(max_attempts=1, window_seconds=10)
    fake_time = [1000.0]
    monkeypatch.setattr("backend.app.auth.rate_limit.time.time", lambda: fake_time[0])

    assert limiter.check("k") is True
    assert limiter.check("k") is False

    fake_time[0] += 11  # past the 10s window
    assert limiter.check("k") is True
