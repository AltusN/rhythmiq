"""
Test cases for the routine router.
Key differences from other routers:
- A routine belongs to exactly one meet entry (entry_id), pre-checked for
  existence on create since SQLite FK enforcement isn't guaranteed on in
  the real app.
- apparatus + entry_id is unique (one row per apparatus per entry).
- Routines can be filtered by entry_id when listing.
- PATCH only ever touches order_of_performance — entry_id/apparatus are
  locked in at creation.
"""

from app.models import Apparatus
from test.conftest import make_gymnast, make_meet, make_meet_entry, make_routine


def _entry(db_session):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    return make_meet_entry(db_session, meet, gymnast=gymnast)


##-- POST /routines --##
def test_create_routine_happy_path(client, db_session):
    entry = _entry(db_session)
    db_session.commit()

    response = client.post(
        "/routines",
        json={"entry_id": entry.id, "apparatus": "hoop", "order_of_performance": 1},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["entry_id"] == entry.id
    assert body["apparatus"] == "hoop"
    assert body["order_of_performance"] == 1
    assert "id" in body


def test_create_routine_without_order_of_performance(client, db_session):
    entry = _entry(db_session)
    db_session.commit()

    response = client.post("/routines", json={"entry_id": entry.id, "apparatus": "ball"})

    assert response.status_code == 201
    assert response.json()["order_of_performance"] is None


def test_create_routine_entry_not_found(client, db_session):
    response = client.post(
        "/routines",
        json={"entry_id": 9999, "apparatus": "hoop"},
    )
    assert response.status_code == 404
    assert "entry" in response.json()["detail"].lower()


def test_create_routine_duplicate_apparatus_for_entry(client, db_session):
    entry = _entry(db_session)
    make_routine(db_session, entry, apparatus=Apparatus.ribbon)
    db_session.commit()

    response = client.post(
        "/routines",
        json={"entry_id": entry.id, "apparatus": "ribbon"},
    )
    assert response.status_code == 409


##-- GET /routines and GET /routines/{id} --##
def test_list_routines_empty(client):
    response = client.get("/routines")
    assert response.status_code == 200
    assert response.json() == []


def test_list_routines_returns_all(client, db_session):
    entry = _entry(db_session)
    make_routine(db_session, entry, apparatus=Apparatus.hoop)
    make_routine(db_session, entry, apparatus=Apparatus.ball)
    db_session.commit()

    response = client.get("/routines")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_routines_filter_by_entry_id(client, db_session):
    entry1 = _entry(db_session)
    gymnast2 = make_gymnast(db_session, first_name="Second", last_name="Gymnast")
    entry2 = make_meet_entry(db_session, make_meet(db_session), gymnast=gymnast2, bib_number="A2")
    make_routine(db_session, entry1, apparatus=Apparatus.hoop)
    make_routine(db_session, entry2, apparatus=Apparatus.ball)
    db_session.commit()

    response = client.get(f"/routines?entry_id={entry1.id}")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["entry_id"] == entry1.id


def test_get_routine_returns_one(client, db_session):
    entry = _entry(db_session)
    routine = make_routine(db_session, entry, apparatus=Apparatus.clubs)
    db_session.commit()

    response = client.get(f"/routines/{routine.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == routine.id
    assert body["apparatus"] == "clubs"


def test_get_routine_not_found(client):
    response = client.get("/routines/9999")
    assert response.status_code == 404


##-- PATCH /routines/{id} --##
def test_update_routine_order_of_performance(client, db_session):
    entry = _entry(db_session)
    routine = make_routine(db_session, entry, apparatus=Apparatus.rope)
    db_session.commit()

    response = client.patch(f"/routines/{routine.id}", json={"order_of_performance": 3})

    assert response.status_code == 200
    assert response.json()["order_of_performance"] == 3


def test_update_routine_not_found(client):
    response = client.patch("/routines/9999", json={"order_of_performance": 1})
    assert response.status_code == 404


def test_update_routine_body_is_empty(client, db_session):
    entry = _entry(db_session)
    routine = make_routine(db_session, entry, apparatus=Apparatus.freehand)
    db_session.commit()

    response = client.patch(f"/routines/{routine.id}", json={})
    assert response.status_code == 200


def test_update_routine_entry_id_field_is_ignored(client, db_session):
    # entry_id is not part of RoutineUpdate, so sending it should have no effect.
    entry = _entry(db_session)
    routine = make_routine(db_session, entry, apparatus=Apparatus.freehand)
    db_session.commit()

    response = client.patch(
        f"/routines/{routine.id}",
        json={"entry_id": 9999, "order_of_performance": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["entry_id"] == entry.id
    assert body["order_of_performance"] == 2


##-- DELETE /routines/{id} --##
def test_delete_routine_success(client, db_session):
    entry = _entry(db_session)
    routine = make_routine(db_session, entry, apparatus=Apparatus.hoop)
    db_session.commit()

    response = client.delete(f"/routines/{routine.id}")
    assert response.status_code == 204

    get_response = client.get(f"/routines/{routine.id}")
    assert get_response.status_code == 404


def test_delete_routine_not_found(client):
    response = client.delete("/routines/9999")
    assert response.status_code == 404
