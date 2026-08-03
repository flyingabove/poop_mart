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


def _make_series_and_figures(conn, n: int) -> list[str]:
    conn.execute(
        "INSERT INTO series (id, name, brand_line) VALUES ('s1', 'Test Series', 'Test Brand')"
    )
    figure_ids = [f"fig{i}" for i in range(n)]
    for fid in figure_ids:
        conn.execute(
            "INSERT INTO figures (id, series_id, name) VALUES (?, 's1', ?)", (fid, fid)
        )
    return figure_ids


def _make_review(conn, review_id: int, reviewer_id: str, figure_id: str, created_at: int) -> None:
    conn.execute(
        "INSERT INTO reviews (id, user_id, figure_id, rating, text, created_at) VALUES (?, ?, ?, 5, 'x', ?)",
        (review_id, reviewer_id, figure_id, created_at),
    )


def _vote(conn, voter_id: str, review_id: int, direction: str) -> None:
    conn.execute(
        "INSERT INTO review_votes (user_id, review_id, direction, created_at) VALUES (?, ?, ?, 1000)",
        (voter_id, review_id, direction),
    )


def test_top_reviewer_requires_volume_and_net_helpful_votes(isolated_db, monkeypatch):
    monkeypatch.setattr(badges_service, "TOP_REVIEWER_THRESHOLD", 3)
    monkeypatch.setattr(badges_service, "TOP_REVIEWER_MIN_NET_HELPFUL", 1)

    conn = db_module.get_connection()
    _make_user(conn, "prolific_but_unvoted", 100)
    _make_user(conn, "prolific_and_helpful", 200)
    _make_user(conn, "voter", 300)
    figure_ids = _make_series_and_figures(conn, 3)

    for i, fid in enumerate(figure_ids):
        _make_review(conn, i + 1, "prolific_but_unvoted", fid, 100)
    for i, fid in enumerate(figure_ids):
        _make_review(conn, i + 10, "prolific_and_helpful", fid, 200)
    _vote(conn, "voter", 10, "helpful")
    conn.commit()
    conn.close()

    # 3 reviews, zero votes -- volume alone is not enough anymore.
    assert "top_reviewer" not in [b["code"] for b in badges_service.get_badges("prolific_but_unvoted")]
    # 3 reviews and one net-helpful vote -- both conditions met.
    assert "top_reviewer" in [b["code"] for b in badges_service.get_badges("prolific_and_helpful")]


def test_top_reviewer_not_granted_below_volume_threshold_even_with_votes(isolated_db, monkeypatch):
    monkeypatch.setattr(badges_service, "TOP_REVIEWER_THRESHOLD", 3)
    monkeypatch.setattr(badges_service, "TOP_REVIEWER_MIN_NET_HELPFUL", 1)

    conn = db_module.get_connection()
    _make_user(conn, "well_voted_but_light", 100)
    _make_user(conn, "voter_a", 300)
    _make_user(conn, "voter_b", 400)
    figure_ids = _make_series_and_figures(conn, 2)

    _make_review(conn, 1, "well_voted_but_light", figure_ids[0], 100)
    _make_review(conn, 2, "well_voted_but_light", figure_ids[1], 100)
    _vote(conn, "voter_a", 1, "helpful")
    _vote(conn, "voter_b", 2, "helpful")
    conn.commit()
    conn.close()

    # Only 2 reviews (threshold is 3), despite plenty of net-helpful votes.
    assert "top_reviewer" not in [b["code"] for b in badges_service.get_badges("well_voted_but_light")]


def test_top_reviewer_net_helpful_subtracts_unhelpful_votes(isolated_db, monkeypatch):
    monkeypatch.setattr(badges_service, "TOP_REVIEWER_THRESHOLD", 1)
    monkeypatch.setattr(badges_service, "TOP_REVIEWER_MIN_NET_HELPFUL", 1)

    conn = db_module.get_connection()
    _make_user(conn, "mixed_votes", 100)
    _make_user(conn, "voter_a", 200)
    _make_user(conn, "voter_b", 300)
    figure_ids = _make_series_and_figures(conn, 1)

    _make_review(conn, 1, "mixed_votes", figure_ids[0], 100)
    _vote(conn, "voter_a", 1, "helpful")
    _vote(conn, "voter_b", 1, "unhelpful")
    conn.commit()
    conn.close()

    # Net helpful = 1 - 1 = 0, below the minimum of 1.
    assert "top_reviewer" not in [b["code"] for b in badges_service.get_badges("mixed_votes")]
