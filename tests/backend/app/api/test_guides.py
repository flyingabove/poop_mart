def test_get_guide_returns_figure_signatures(client):
    r = client.get("/api/guides/labubu-forest-party")
    assert r.status_code == 200
    data = r.json()
    assert data["series_id"] == "labubu-forest-party"
    assert data["figure_signatures"], "seeded guide should have figure signatures"
    sig = data["figure_signatures"][0]
    assert "confidence_score" in sig
    assert 0 <= sig["confidence_score"] <= 100


def test_get_guide_for_series_without_guide_returns_placeholder(client):
    r = client.get("/api/guides/molly-space-travel")
    assert r.status_code == 200
    data = r.json()
    assert data["figure_signatures"] == []


def test_get_guide_unknown_series_404s(client):
    r = client.get("/api/guides/does-not-exist")
    assert r.status_code == 404


def _auth_headers(client, email="voter1@example.com"):
    r = client.post("/api/auth/signup", json={"email": email, "password": "hunter2222"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_add_contribution_and_reflect_in_guide(client):
    headers = _auth_headers(client, "contributor1@example.com")
    r = client.post(
        "/api/guides/labubu-forest-party/contributions",
        json={
            "figure_id": "lfp-pinecone-guard",
            "technique_type": "weight",
            "claim_text": "Measured 46g on a digital scale.",
            "weight_range_g": "46-48g",
        },
        headers=headers,
    )
    assert r.status_code == 201

    r2 = client.get("/api/guides/labubu-forest-party")
    pinecone = next(s for s in r2.json()["figure_signatures"] if s["figure_id"] == "lfp-pinecone-guard")
    assert pinecone["contribution_count"] >= 2  # seed already had 1


def test_add_contribution_requires_auth(client):
    r = client.post(
        "/api/guides/labubu-forest-party/contributions",
        json={"figure_id": "lfp-pinecone-guard", "technique_type": "weight", "claim_text": "no auth header"},
    )
    assert r.status_code == 401


def test_add_contribution_is_attributed_to_the_poster(client):
    headers = _auth_headers(client, "contributor2@example.com")
    client.post(
        "/api/guides/labubu-forest-party/contributions",
        json={"figure_id": "lfp-berry-picker", "technique_type": "sound", "claim_text": "faint rattle"},
        headers=headers,
    )

    data = client.get("/api/guides/labubu-forest-party").json()
    mine = next(c for c in data["contributions"] if c["claim_text"] == "faint rattle")
    assert mine["contributor"] == "contributor2"  # local part of the email, not the full address
    assert "@" not in mine["contributor"]


def test_add_contribution_with_video_url(client):
    # SHAKE_GUIDES_DESIGN.md documents video_url as a first-class
    # GuideContribution field ("demonstration clip"); the API has always
    # accepted and returned it, previously with no test coverage at all.
    headers = _auth_headers(client, "contributor-video@example.com")
    client.post(
        "/api/guides/labubu-forest-party/contributions",
        json={
            "figure_id": "lfp-acorn-hoarder",
            "technique_type": "sound",
            "claim_text": "distinct rattle, see clip",
            "video_url": "https://example.com/demo-clip",
        },
        headers=headers,
    )

    data = client.get("/api/guides/labubu-forest-party").json()
    mine = next(c for c in data["contributions"] if c["claim_text"] == "distinct rattle, see clip")
    assert mine["video_url"] == "https://example.com/demo-clip"


def test_add_contribution_without_video_url_is_null(client):
    headers = _auth_headers(client, "contributor-novideo@example.com")
    client.post(
        "/api/guides/labubu-forest-party/contributions",
        json={"figure_id": "lfp-acorn-hoarder", "technique_type": "weight", "claim_text": "no video for this one"},
        headers=headers,
    )

    data = client.get("/api/guides/labubu-forest-party").json()
    mine = next(c for c in data["contributions"] if c["claim_text"] == "no video for this one")
    assert mine["video_url"] is None


def test_box_code_and_seam_contributions_appear_as_distinguishing_notes(client):
    # SHAKE_GUIDES_DESIGN.md's figure_signatures structure documents a
    # distinguishing_notes field specifically for seam/box-code tells --
    # get_guide() previously only ever surfaced weight_range_g and
    # sound_description in a signature, so a fully-submittable,
    # confidence-counted box_code or seam contribution's actual claim
    # content never appeared anywhere in the guide's headline signature
    # view (only in the raw, unaggregated contributions list below it).
    # crybaby-crying-again has no seeded guide at all and isn't touched by
    # any other test in this file, so it starts genuinely clean.
    headers = _auth_headers(client, "contributor-boxcode@example.com")
    r = client.post(
        "/api/guides/crybaby-crying-again/contributions",
        json={"figure_id": "cb-tears", "technique_type": "box_code", "claim_text": "box code ends in 7F"},
        headers=headers,
    )
    assert r.status_code == 201
    r2 = client.post(
        "/api/guides/crybaby-crying-again/contributions",
        json={
            "figure_id": "cb-tears",
            "technique_type": "seam",
            "claim_text": "sticker seam slightly offset on the left edge",
        },
        headers=headers,
    )
    assert r2.status_code == 201

    data = client.get("/api/guides/crybaby-crying-again").json()
    sig = next(s for s in data["figure_signatures"] if s["figure_id"] == "cb-tears")
    assert sig["distinguishing_notes"] is not None
    assert "box code ends in 7F" in sig["distinguishing_notes"]
    assert "sticker seam slightly offset on the left edge" in sig["distinguishing_notes"]
    # no weight/sound claim was ever made for this figure -- those fields stay null.
    assert sig["weight_range_g"] is None
    assert sig["sound_description"] is None


def test_weight_only_signature_has_no_distinguishing_notes(client):
    # A figure signature built only from weight/sound claims shouldn't
    # gain a phantom distinguishing_notes value -- regression guard for
    # the box_code/seam aggregation above. skullpanda-city-of-night also
    # has no seeded guide and isn't touched elsewhere in this file.
    headers = _auth_headers(client, "contributor-weightonly@example.com")
    r = client.post(
        "/api/guides/skullpanda-city-of-night/contributions",
        json={
            "figure_id": "sp-nightwatch",
            "technique_type": "weight",
            "claim_text": "51g on my scale",
            "weight_range_g": "50-52g",
        },
        headers=headers,
    )
    assert r.status_code == 201

    data = client.get("/api/guides/skullpanda-city-of-night").json()
    sig = next(s for s in data["figure_signatures"] if s["figure_id"] == "sp-nightwatch")
    assert sig["distinguishing_notes"] is None


def test_seeded_distinguishing_notes_now_reach_the_signature(client):
    # The seed data always wrote a per-figure distinguishing_notes string
    # (backend/app/db/seed.py's _SHAKE_SIGNATURES) but previously discarded
    # it (`_notes`, unused) rather than inserting it as a real contribution
    # -- so even the flagship, fully-populated Labubu Forest Party guide
    # never actually exercised this field. Confirms the seed fix, not just
    # the aggregation logic: lfp-forest-ranger's known seed text should now
    # show up verbatim.
    data = client.get("/api/guides/labubu-forest-party").json()
    sig = next(s for s in data["figure_signatures"] if s["figure_id"] == "lfp-forest-ranger")
    assert sig["distinguishing_notes"] is not None
    assert "Solid pose, no loose parts." in sig["distinguishing_notes"]


def test_seeded_contributions_have_no_contributor(client):
    # Seed-era contributions predate auth and are never backfilled with a user.
    data = client.get("/api/guides/labubu-forest-party").json()
    assert any(c["contributor"] is None for c in data["contributions"])


def test_add_contribution_rejects_unknown_technique(client):
    headers = _auth_headers(client, "contributor3@example.com")
    r = client.post(
        "/api/guides/labubu-forest-party/contributions",
        json={
            "figure_id": "lfp-pinecone-guard",
            "technique_type": "x-ray",
            "claim_text": "not a real technique",
        },
        headers=headers,
    )
    assert r.status_code == 422


def _first_contribution_id(client):
    data = client.get("/api/guides/labubu-forest-party").json()
    return data["contributions"][0]["id"]


def test_vote_requires_auth(client):
    contribution_id = _first_contribution_id(client)
    r = client.post(f"/api/guides/contributions/{contribution_id}/vote", json={"direction": "up"})
    assert r.status_code == 401


def test_vote_up_increases_upvotes(client):
    contribution_id = _first_contribution_id(client)
    before = next(
        c for c in client.get("/api/guides/labubu-forest-party").json()["contributions"] if c["id"] == contribution_id
    )
    headers = _auth_headers(client, "voter2@example.com")
    r = client.post(f"/api/guides/contributions/{contribution_id}/vote", json={"direction": "up"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["upvotes"] == before["upvotes"] + 1


def test_changing_vote_does_not_double_count(client):
    contribution_id = _first_contribution_id(client)
    headers = _auth_headers(client, "voter3@example.com")
    up_result = client.post(
        f"/api/guides/contributions/{contribution_id}/vote", json={"direction": "up"}, headers=headers
    ).json()
    down_result = client.post(
        f"/api/guides/contributions/{contribution_id}/vote", json={"direction": "down"}, headers=headers
    ).json()
    # Switching this user's vote from up to down should move exactly one
    # vote, not add a second -- upvotes drops back down, downvotes rises by one.
    assert down_result["upvotes"] == up_result["upvotes"] - 1
    assert down_result["downvotes"] == up_result["downvotes"] + 1


def test_vote_rejects_invalid_direction(client):
    contribution_id = _first_contribution_id(client)
    headers = _auth_headers(client, "voter4@example.com")
    r = client.post(
        f"/api/guides/contributions/{contribution_id}/vote", json={"direction": "sideways"}, headers=headers
    )
    assert r.status_code == 422


def test_vote_unknown_contribution_422s(client):
    headers = _auth_headers(client, "voter5@example.com")
    r = client.post("/api/guides/contributions/999999/vote", json={"direction": "up"}, headers=headers)
    assert r.status_code == 422


def test_my_vote_reflected_in_guide_response(client):
    contribution_id = _first_contribution_id(client)
    headers = _auth_headers(client, "voter6@example.com")
    client.post(f"/api/guides/contributions/{contribution_id}/vote", json={"direction": "up"}, headers=headers)

    data = client.get("/api/guides/labubu-forest-party", headers=headers).json()
    mine = next(c for c in data["contributions"] if c["id"] == contribution_id)
    assert mine["my_vote"] == "up"

    # anonymous request to the same guide shouldn't see a my_vote
    anon_data = client.get("/api/guides/labubu-forest-party").json()
    anon_mine = next(c for c in anon_data["contributions"] if c["id"] == contribution_id)
    assert anon_mine["my_vote"] is None


def test_remove_own_contribution(client):
    headers = _auth_headers(client, "remover1@example.com")
    r = client.post(
        "/api/guides/labubu-forest-party/contributions",
        json={"figure_id": "lfp-pinecone-guard", "technique_type": "weight", "claim_text": "48g on my scale"},
        headers=headers,
    )
    contribution_id = r.json()["id"]

    r2 = client.delete(f"/api/guides/contributions/{contribution_id}", headers=headers)
    assert r2.status_code == 200

    data = client.get("/api/guides/labubu-forest-party").json()
    assert not any(c["id"] == contribution_id for c in data["contributions"])


def test_remove_contribution_requires_auth(client):
    contribution_id = _first_contribution_id(client)
    r = client.delete(f"/api/guides/contributions/{contribution_id}")
    assert r.status_code == 401


def test_cannot_remove_other_users_contribution(client):
    headers_a = _auth_headers(client, "remover2a@example.com")
    headers_b = _auth_headers(client, "remover2b@example.com")
    r = client.post(
        "/api/guides/labubu-forest-party/contributions",
        json={"figure_id": "lfp-pinecone-guard", "technique_type": "sound", "claim_text": "click sound"},
        headers=headers_a,
    )
    contribution_id = r.json()["id"]

    r2 = client.delete(f"/api/guides/contributions/{contribution_id}", headers=headers_b)
    assert r2.status_code == 404

    # still there for the actual owner
    data = client.get("/api/guides/labubu-forest-party").json()
    assert any(c["id"] == contribution_id for c in data["contributions"])


def test_cannot_remove_seeded_contribution(client):
    # Seed-era contributions have no user_id -- nobody is authenticated as
    # their author, so they can never be removed via this route. Find one
    # by contributor == None explicitly rather than assuming list order,
    # since other tests in this shared-DB suite add newer contributions.
    data = client.get("/api/guides/labubu-forest-party").json()
    seeded = next(c for c in data["contributions"] if c["contributor"] is None)
    headers = _auth_headers(client, "remover3@example.com")
    r = client.delete(f"/api/guides/contributions/{seeded['id']}", headers=headers)
    assert r.status_code == 404


def test_remove_unknown_contribution_404s(client):
    headers = _auth_headers(client, "remover4@example.com")
    r = client.delete("/api/guides/contributions/999999", headers=headers)
    assert r.status_code == 404


def test_voting_raises_confidence_score(client):
    contribution_id = _first_contribution_id(client)
    figure_id = next(
        c["figure_id"] for c in client.get("/api/guides/labubu-forest-party").json()["contributions"]
        if c["id"] == contribution_id
    )
    before = next(
        s for s in client.get("/api/guides/labubu-forest-party").json()["figure_signatures"]
        if s["figure_id"] == figure_id
    )
    headers = _auth_headers(client, "voter7@example.com")
    client.post(f"/api/guides/contributions/{contribution_id}/vote", json={"direction": "up"}, headers=headers)

    after = next(
        s for s in client.get("/api/guides/labubu-forest-party").json()["figure_signatures"]
        if s["figure_id"] == figure_id
    )
    assert after["confidence_score"] >= before["confidence_score"]


# labubu-macaron (lm-vanilla / lm-pistachio) has no seeded guide or
# contributions and no other test in this suite touches its guide -- a
# clean series to test the contribution-count-crosses-threshold feed card
# trigger from a known-zero starting point. Written as one self-contained
# test (not several relying on shared state across test functions) since
# pytest execution order across functions shouldn't be load-bearing.

def test_shake_guide_feed_card_appears_on_threshold_and_updates_after(client):
    headers = _auth_headers(client, "guidecard-flow@example.com")
    follower_headers = _auth_headers(client, "guidecard-follower@example.com")
    client.post("/api/follows/series/labubu-macaron", headers=follower_headers)

    def _post(figure_id, claim):
        r = client.post(
            "/api/guides/labubu-macaron/contributions",
            json={"figure_id": figure_id, "technique_type": "weight", "claim_text": claim},
            headers=headers,
        )
        assert r.status_code == 201

    def _card():
        data = client.get("/api/feed", params={"card_type": "shake_guide"}).json()
        matches = [c for c in data["cards"] if c["series_id"] == "labubu-macaron"]
        assert len(matches) <= 1, "should update the same card in place, never duplicate"
        return matches[0] if matches else None

    def _guide_notif_count():
        data = client.get("/api/notifications", headers=follower_headers).json()
        return sum(1 for n in data["notifications"] if n.get("series_id") == "labubu-macaron")

    _post("lm-vanilla", "45g")
    _post("lm-pistachio", "44g")
    assert _card() is None, "below SHAKE_GUIDE_CARD_THRESHOLD (3) -- no card yet"
    assert _guide_notif_count() == 0, "no notification below threshold"

    _post("lm-vanilla", "faint rattle")
    card = _card()
    assert card is not None, "3rd contribution crosses the threshold"
    assert "Labubu Macaron" in card["title"]
    assert "3 community tells" in card["body"]
    assert _guide_notif_count() == 1, "a series-follower is notified exactly once, on the crossing"
    notif_data = client.get("/api/notifications", headers=follower_headers).json()
    guide_notif = next(n for n in notif_data["notifications"] if n.get("series_id") == "labubu-macaron")
    assert guide_notif["notification_type"] == "shake_guide_update", (
        "a real Shake Guide threshold-crossing notification must use its own category, "
        "independently controllable from general followed-series updates"
    )

    _post("lm-pistachio", "code ends in 7")
    card = _card()
    assert "4 community tells" in card["body"], "card updates in place on further contributions"
    assert _guide_notif_count() == 1, "no repeat notification for contributions after the initial crossing"
