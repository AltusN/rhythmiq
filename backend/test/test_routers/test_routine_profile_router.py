"""
Test cases for the routine profile router.
Key differences from other routers:
- A profile belongs to exactly one of gymnast_id/group_id, enforced by the
  schema's model_validator before the request ever reaches the router.
- Profiles can be filtered by gymnast_id, group_id, apparatus, and level
  when listing.
- PATCH only ever touches music_url/choreography_notes — gymnast_id,
  group_id, apparatus, and level are locked in at creation.
"""

from app.models import Apparatus, Level
from test.conftest import make_club, make_district, make_group, make_gymnast, make_routine_profile


def _gymnast(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    return make_gymnast(db_session, club=club)


##-- POST /routine-profiles --##
def test_create_routine_profile_with_gymnast_happy_path(client, db_session):
    gymnast = _gymnast(db_session)

    response = client.post(
        "/routine-profiles",
        json={
            "gymnast_id": gymnast.id,
            "apparatus": "hoop",
            "level": "level_3",
            "music_url": "https://example.com/hoop.mp3",
            "choreography_notes": "Spin sequence at the midpoint.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["gymnast_id"] == gymnast.id
    assert body["group_id"] is None
    assert body["apparatus"] == "hoop"
    assert body["level"] == "level_3"
    assert body["music_url"] == "https://example.com/hoop.mp3"
    assert body["choreography_notes"] == "Spin sequence at the midpoint."
    assert "id" in body


def test_create_routine_profile_with_group_happy_path(client, db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    group = make_group(db_session, club=club)

    response = client.post(
        "/routine-profiles",
        json={"group_id": group.id, "apparatus": "ball", "level": "level_4"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["group_id"] == group.id
    assert body["gymnast_id"] is None


def test_create_routine_profile_missing_gymnast_and_group_fails(client):
    response = client.post("/routine-profiles", json={"apparatus": "hoop", "level": "level_3"})
    assert response.status_code == 422


def test_create_routine_profile_both_gymnast_and_group_fails(client, db_session):
    gymnast = _gymnast(db_session)
    group = make_group(db_session, club=make_club(db_session, make_district(db_session)))

    response = client.post(
        "/routine-profiles",
        json={
            "gymnast_id": gymnast.id,
            "group_id": group.id,
            "apparatus": "hoop",
            "level": "level_3",
        },
    )
    assert response.status_code == 422


def test_create_routine_profile_gymnast_not_found(client):
    response = client.post(
        "/routine-profiles",
        json={"gymnast_id": 9999, "apparatus": "hoop", "level": "level_3"},
    )
    assert response.status_code == 404
    assert "gymnast" in response.json()["detail"].lower()


def test_create_routine_profile_group_not_found(client):
    response = client.post(
        "/routine-profiles",
        json={"group_id": 9999, "apparatus": "hoop", "level": "level_3"},
    )
    assert response.status_code == 404
    assert "group" in response.json()["detail"].lower()


def test_create_routine_profile_duplicate_gymnast_apparatus_level(client, db_session):
    gymnast = _gymnast(db_session)
    make_routine_profile(db_session, gymnast=gymnast, apparatus=Apparatus.hoop, level=Level.level_3)
    db_session.commit()

    response = client.post(
        "/routine-profiles",
        json={"gymnast_id": gymnast.id, "apparatus": "hoop", "level": "level_3"},
    )
    assert response.status_code == 409


def test_create_routine_profile_duplicate_group_apparatus_level(client, db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    group = make_group(db_session, club=club)
    make_routine_profile(db_session, group=group, apparatus=Apparatus.ball, level=Level.level_4)
    db_session.commit()

    response = client.post(
        "/routine-profiles",
        json={"group_id": group.id, "apparatus": "ball", "level": "level_4"},
    )
    assert response.status_code == 409


##-- GET /routine-profiles and GET /routine-profiles/{id} --##
def test_list_routine_profiles_empty(client):
    response = client.get("/routine-profiles")
    assert response.status_code == 200
    assert response.json() == []


def test_list_routine_profiles_returns_all(client, db_session):
    gymnast = _gymnast(db_session)
    make_routine_profile(db_session, gymnast=gymnast, apparatus=Apparatus.hoop)
    make_routine_profile(db_session, gymnast=gymnast, apparatus=Apparatus.ball)
    db_session.commit()

    response = client.get("/routine-profiles")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_routine_profiles_filter_by_gymnast_id(client, db_session):
    gymnast1 = _gymnast(db_session)
    gymnast2 = make_gymnast(db_session, first_name="Second", last_name="Gymnast")
    make_routine_profile(db_session, gymnast=gymnast1, apparatus=Apparatus.hoop)
    make_routine_profile(db_session, gymnast=gymnast2, apparatus=Apparatus.ball)
    db_session.commit()

    response = client.get(f"/routine-profiles?gymnast_id={gymnast1.id}")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["gymnast_id"] == gymnast1.id


def test_list_routine_profiles_filter_by_group_id(client, db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    group = make_group(db_session, club=club)
    gymnast = make_gymnast(db_session, club=club)
    make_routine_profile(db_session, group=group, apparatus=Apparatus.ball)
    make_routine_profile(db_session, gymnast=gymnast, apparatus=Apparatus.hoop)
    db_session.commit()

    response = client.get(f"/routine-profiles?group_id={group.id}")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["group_id"] == group.id


def test_list_routine_profiles_filter_by_apparatus_and_level(client, db_session):
    gymnast = _gymnast(db_session)
    make_routine_profile(db_session, gymnast=gymnast, apparatus=Apparatus.hoop, level=Level.level_3)
    make_routine_profile(db_session, gymnast=gymnast, apparatus=Apparatus.hoop, level=Level.level_4)
    db_session.commit()

    response = client.get("/routine-profiles?apparatus=hoop&level=level_3")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["level"] == "level_3"


def test_get_routine_profile_returns_one(client, db_session):
    gymnast = _gymnast(db_session)
    profile = make_routine_profile(db_session, gymnast=gymnast, apparatus=Apparatus.clubs)
    db_session.commit()

    response = client.get(f"/routine-profiles/{profile.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == profile.id
    assert body["gymnast_id"] == gymnast.id


def test_get_routine_profile_not_found(client):
    response = client.get("/routine-profiles/9999")
    assert response.status_code == 404


##-- PATCH /routine-profiles/{id} --##
def test_update_routine_profile_music_url_and_notes(client, db_session):
    gymnast = _gymnast(db_session)
    profile = make_routine_profile(db_session, gymnast=gymnast, apparatus=Apparatus.rope)
    db_session.commit()

    response = client.patch(
        f"/routine-profiles/{profile.id}",
        json={"music_url": "https://example.com/new.mp3", "choreography_notes": "Updated notes"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["music_url"] == "https://example.com/new.mp3"
    assert body["choreography_notes"] == "Updated notes"


def test_update_routine_profile_not_found(client):
    response = client.patch(
        "/routine-profiles/9999", json={"music_url": "https://example.com/new.mp3"}
    )
    assert response.status_code == 404


def test_update_routine_profile_body_is_empty(client, db_session):
    gymnast = _gymnast(db_session)
    profile = make_routine_profile(db_session, gymnast=gymnast, apparatus=Apparatus.freehand)
    db_session.commit()

    response = client.patch(f"/routine-profiles/{profile.id}", json={})
    assert response.status_code == 200


def test_update_routine_profile_gymnast_id_field_is_ignored(client, db_session):
    # gymnast_id is not part of RoutineProfileUpdate, so sending it should have no effect.
    gymnast = _gymnast(db_session)
    profile = make_routine_profile(db_session, gymnast=gymnast, apparatus=Apparatus.freehand)
    db_session.commit()

    response = client.patch(
        f"/routine-profiles/{profile.id}",
        json={"gymnast_id": 9999, "music_url": "https://example.com/new.mp3"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["gymnast_id"] == gymnast.id
    assert body["music_url"] == "https://example.com/new.mp3"


##-- DELETE /routine-profiles/{id} --##
def test_delete_routine_profile_success(client, db_session):
    gymnast = _gymnast(db_session)
    profile = make_routine_profile(db_session, gymnast=gymnast, apparatus=Apparatus.hoop)
    db_session.commit()

    response = client.delete(f"/routine-profiles/{profile.id}")
    assert response.status_code == 204

    get_response = client.get(f"/routine-profiles/{profile.id}")
    assert get_response.status_code == 404


def test_delete_routine_profile_not_found(client):
    response = client.delete("/routine-profiles/9999")
    assert response.status_code == 404
