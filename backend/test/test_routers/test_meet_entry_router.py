"""
Test cases for the meet entry router.
Key differences from other routers:
- A meet entry belongs to exactly one of gymnast_id/group_id, enforced by
  the schema's model_validator before the request ever reaches the router.
- Meet entries can be filtered by meet_id, gymnast_id, and group_id when listing.
- PATCH has no FK fields at all — meet_id/gymnast_id/group_id are locked in at creation.
"""

from test.conftest import (
    make_club,
    make_district,
    make_group,
    make_gymnast,
    make_meet,
    make_meet_entry,
    make_routine,
)


def _meet_and_gymnast(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    meet = make_meet(db_session, district=district)
    gymnast = make_gymnast(db_session, club=club)
    return meet, gymnast


##-- POST /meet-entries --##
def test_create_meet_entry_with_gymnast_happy_path(client, db_session):
    meet, gymnast = _meet_and_gymnast(db_session)

    response = client.post(
        "/meet-entries",
        json={
            "meet_id": meet.id,
            "gymnast_id": gymnast.id,
            "level": "level_3",
            "age_group": "u12",
            "bib_number": "A123",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["meet_id"] == meet.id
    assert body["gymnast_id"] == gymnast.id
    assert body["group_id"] is None
    assert body["level"] == "level_3"
    assert body["age_group"] == "u12"
    assert body["bib_number"] == "A123"
    assert body["entry_fee_paid"] is False
    assert "id" in body


def test_create_meet_entry_with_group_happy_path(client, db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    meet = make_meet(db_session, district=district)
    group = make_group(db_session, club=club)

    response = client.post(
        "/meet-entries",
        json={
            "meet_id": meet.id,
            "group_id": group.id,
            "level": "level_3",
            "age_group": "u12",
            "bib_number": "A123",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["meet_id"] == meet.id
    assert body["group_id"] == group.id
    assert body["gymnast_id"] is None


def test_create_meet_entry_missing_gymnast_and_group_fails(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district=district)

    response = client.post(
        "/meet-entries",
        json={
            "meet_id": meet.id,
            "level": "level_3",
            "age_group": "u12",
            "bib_number": "A123",
        },
    )
    assert response.status_code == 422


def test_create_meet_entry_both_gymnast_and_group_fails(client, db_session):
    meet, gymnast = _meet_and_gymnast(db_session)
    group = make_group(db_session, club=make_club(db_session, make_district(db_session)))

    response = client.post(
        "/meet-entries",
        json={
            "meet_id": meet.id,
            "gymnast_id": gymnast.id,
            "group_id": group.id,
            "level": "level_3",
            "age_group": "u12",
            "bib_number": "A123",
        },
    )
    assert response.status_code == 422


def test_create_meet_entry_meet_not_found(client, db_session):
    _, gymnast = _meet_and_gymnast(db_session)

    response = client.post(
        "/meet-entries",
        json={
            "meet_id": 9999,
            "gymnast_id": gymnast.id,
            "level": "level_3",
            "age_group": "u12",
            "bib_number": "A123",
        },
    )
    assert response.status_code == 404
    assert "meet" in response.json()["detail"].lower()


def test_create_meet_entry_gymnast_not_found(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district=district)

    response = client.post(
        "/meet-entries",
        json={
            "meet_id": meet.id,
            "gymnast_id": 9999,
            "level": "level_3",
            "age_group": "u12",
            "bib_number": "A123",
        },
    )
    assert response.status_code == 404
    assert "gymnast" in response.json()["detail"].lower()


def test_create_meet_entry_group_not_found(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district=district)

    response = client.post(
        "/meet-entries",
        json={
            "meet_id": meet.id,
            "group_id": 9999,
            "level": "level_3",
            "age_group": "u12",
            "bib_number": "A123",
        },
    )
    assert response.status_code == 404
    assert "group" in response.json()["detail"].lower()


def test_create_meet_entry_duplicate_gymnast_at_meet(client, db_session):
    meet, gymnast = _meet_and_gymnast(db_session)
    make_meet_entry(db_session, meet, gymnast=gymnast)
    db_session.commit()

    response = client.post(
        "/meet-entries",
        json={
            "meet_id": meet.id,
            "gymnast_id": gymnast.id,
            "level": "level_3",
            "age_group": "u12",
            "bib_number": "A123",
        },
    )
    assert response.status_code == 409


def test_create_meet_entry_duplicate_group_at_meet(client, db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    meet = make_meet(db_session, district=district)
    group = make_group(db_session, club=club)
    make_meet_entry(db_session, meet, group=group)
    db_session.commit()

    response = client.post(
        "/meet-entries",
        json={
            "meet_id": meet.id,
            "group_id": group.id,
            "level": "level_3",
            "age_group": "u12",
            "bib_number": "A123",
        },
    )
    assert response.status_code == 409


##-- GET /meet-entries and GET /meet-entries/{id} --##
def test_list_meet_entries_empty(client):
    response = client.get("/meet-entries")
    assert response.status_code == 200
    assert response.json() == []


def test_list_meet_entries_returns_all(client, db_session):
    meet, gymnast = _meet_and_gymnast(db_session)
    gymnast2 = make_gymnast(db_session, first_name="Second", last_name="Gymnast")
    make_meet_entry(db_session, meet, gymnast=gymnast, bib_number="A1")
    make_meet_entry(db_session, meet, gymnast=gymnast2, bib_number="A2")
    db_session.commit()

    response = client.get("/meet-entries")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_meet_entries_filter_by_meet_id(client, db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    meet1 = make_meet(db_session, district=district, name="Meet One")
    meet2 = make_meet(db_session, district=district, name="Meet Two")
    gymnast = make_gymnast(db_session, club=club)
    make_meet_entry(db_session, meet1, gymnast=gymnast, bib_number="A1")
    make_meet_entry(db_session, meet2, gymnast=gymnast, bib_number="A2")
    db_session.commit()

    response = client.get(f"/meet-entries?meet_id={meet1.id}")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["meet_id"] == meet1.id


def test_list_meet_entries_filter_by_gymnast_id(client, db_session):
    meet, gymnast = _meet_and_gymnast(db_session)
    gymnast2 = make_gymnast(db_session, first_name="Second", last_name="Gymnast")
    make_meet_entry(db_session, meet, gymnast=gymnast, bib_number="A1")
    make_meet_entry(db_session, meet, gymnast=gymnast2, bib_number="A2")
    db_session.commit()

    response = client.get(f"/meet-entries?gymnast_id={gymnast.id}")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["gymnast_id"] == gymnast.id


def test_list_meet_entries_filter_by_group_id(client, db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    meet = make_meet(db_session, district=district)
    group = make_group(db_session, club=club)
    gymnast = make_gymnast(db_session, club=club)
    make_meet_entry(db_session, meet, group=group)
    make_meet_entry(db_session, meet, gymnast=gymnast, bib_number="A2")
    db_session.commit()

    response = client.get(f"/meet-entries?group_id={group.id}")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["group_id"] == group.id


def test_get_meet_entry_returns_one(client, db_session):
    meet, gymnast = _meet_and_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast=gymnast)
    db_session.commit()

    response = client.get(f"/meet-entries/{entry.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == entry.id
    assert body["gymnast_id"] == gymnast.id


def test_get_meet_entry_not_found(client):
    response = client.get("/meet-entries/9999")
    assert response.status_code == 404


##-- PATCH /meet-entries/{id} --##
def test_update_meet_entry_success(client, db_session):
    meet, gymnast = _meet_and_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast=gymnast)
    db_session.commit()

    response = client.patch(
        f"/meet-entries/{entry.id}",
        json={"bib_number": "Z999", "entry_fee_paid": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["bib_number"] == "Z999"
    assert body["entry_fee_paid"] is True


def test_update_meet_entry_level_and_age_group(client, db_session):
    meet, gymnast = _meet_and_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast=gymnast)
    db_session.commit()

    response = client.patch(
        f"/meet-entries/{entry.id}",
        json={"level": "senior", "age_group": "o14"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["level"] == "senior"
    assert body["age_group"] == "o14"


def test_update_meet_entry_not_found(client):
    response = client.patch("/meet-entries/9999", json={"bib_number": "Z999"})
    assert response.status_code == 404


def test_update_meet_entry_body_is_empty(client, db_session):
    meet, gymnast = _meet_and_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast=gymnast)
    db_session.commit()

    response = client.patch(f"/meet-entries/{entry.id}", json={})
    assert response.status_code == 200


def test_update_meet_entry_gymnast_id_field_is_ignored(client, db_session):
    # gymnast_id is not part of MeetEntryUpdate, so sending it should have no effect.
    meet, gymnast = _meet_and_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast=gymnast)
    db_session.commit()

    response = client.patch(
        f"/meet-entries/{entry.id}",
        json={"gymnast_id": 9999, "bib_number": "Z999"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["gymnast_id"] == gymnast.id
    assert body["bib_number"] == "Z999"


##-- DELETE /meet-entries/{id} --##
def test_delete_meet_entry_success(client, db_session):
    meet, gymnast = _meet_and_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast=gymnast)
    db_session.commit()

    response = client.delete(f"/meet-entries/{entry.id}")
    assert response.status_code == 204

    get_response = client.get(f"/meet-entries/{entry.id}")
    assert get_response.status_code == 404


def test_delete_meet_entry_cascades_to_routines(client, db_session):
    meet, gymnast = _meet_and_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast=gymnast)
    routine = make_routine(db_session, entry)
    db_session.commit()
    routine_id = routine.id

    response = client.delete(f"/meet-entries/{entry.id}")
    assert response.status_code == 204

    from app.models import Routine

    assert db_session.get(Routine, routine_id) is None


def test_delete_meet_entry_not_found(client):
    response = client.delete("/meet-entries/9999")
    assert response.status_code == 404
