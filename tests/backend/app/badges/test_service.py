"""
Early Adopter is rank-based across *all* users in the DB, which makes it
unsafe to test through the shared `client` fixture -- the whole pytest
session accumulates many signups across every test file, and asserting
"the Nth signup is/isn't an early adopter" would be silently dependent on
how many other tests happened to run first. Uses an isolated, empty DB
instead so the user counts in these tests are exact and deterministic.
"""
import pytest

from backend.app.db import database as db_module
from backend.app.badges import service as badges_service


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    db_module.init_db()
    yield


def _make_user(conn, user_id: str, created_at: int) -> None:
    conn.execute(
        "INSERT INTO users (id, email, password_salt, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, f"{user_id}@example.com", "salt", "hash", created_at),
    )


def test_early_adopter_within_cutoff(isolated_db, monkeypatch):
    monkeypatch.setattr(badges_service, "EARLY_ADOPTER_RANK_CUTOFF", 3)

    conn = db_module.get_connection()
    _make_user(conn, "u1", 100)
    _make_user(conn, "u2", 200)
    _make_user(conn, "u3", 300)
    _make_user(conn, "u4", 400)
    conn.commit()
    conn.close()

    badges_u1 = [b["code"] for b in badges_service.get_badges("u1")]
    badges_u3 = [b["code"] for b in badges_service.get_badges("u3")]
    badges_u4 = [b["code"] for b in badges_service.get_badges("u4")]

    assert "early_adopter" in badges_u1  # 1st signup, well within cutoff of 3
    assert "early_adopter" in badges_u3  # 3rd signup, exactly at cutoff
    assert "early_adopter" not in badges_u4  # 4th signup, past cutoff of 3


def test_early_adopter_ties_count_together(isolated_db, monkeypatch):
    monkeypatch.setattr(badges_service, "EARLY_ADOPTER_RANK_CUTOFF", 2)

    conn = db_module.get_connection()
    _make_user(conn, "tie1", 500)
    _make_user(conn, "tie2", 500)  # same created_at -- both should count as rank <= 2
    conn.commit()
    conn.close()

    assert "early_adopter" in [b["code"] for b in badges_service.get_badges("tie1")]
    assert "early_adopter" in [b["code"] for b in badges_service.get_badges("tie2")]


def test_get_badges_for_unknown_user_returns_empty(isolated_db):
    assert badges_service.get_badges("does-not-exist") == []
