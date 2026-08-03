import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """FastAPI TestClient with lifespan (DB init + seed) triggered via `with`."""
    from backend.app import main

    with TestClient(main.app) as c:
        yield c
