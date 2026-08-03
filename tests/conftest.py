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

    with TestClient(main.app) as c:
        yield c
