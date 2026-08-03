import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
    """FastAPI TestClient with lifespan (DB init + seed) triggered via `with`.

    Ingestion is disabled — tests must never make real network calls (the
    Docker build-time test gate has no business hitting Google News on
    every build, and CI shouldn't depend on network availability at all).
    """
    monkeypatch.setenv("DISABLE_INGESTION", "1")
    from backend.app import main
    from backend.app.api import auth as auth_module

    # The auth rate limiters (rate_limit.py) are process-global singletons
    # by design (see that module's docstring) -- but that means every test
    # in this session shares them via TestClient's fixed fake client IP.
    # Without resetting here, login/signup tests earlier in the suite
    # would silently consume attempts that later tests (including this
    # iteration's dedicated rate-limit tests) depend on being fresh.
    auth_module._login_limiter._hits.clear()
    auth_module._signup_limiter._hits.clear()

    with TestClient(main.app) as c:
        yield c
