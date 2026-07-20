"""
Test cases for the routine router.
Key differences from other routers:
- A routine belongs to exactly one meet entry (entry_id), pre-checked for
  existence on create since SQLite FK enforcement isn't guaranteed on in
  the real app.
- apparatus + entry_id is unique (one row per apparatus per entry).
- Routines can be filtered by entry_id when listing.
- PATCH only ever touches order_of_performance and penalty — entry_id/
  apparatus are locked in at creation.
- GET /{id}/score computes the routine's D/A/E/total live from its
  judge_scores via compute_routine_score (app/scoring.py) — the heavy
  scoring logic itself is unit-tested in test_scoring.py, so these tests
  only need to prove the endpoint wires that logic up correctly (404s,
  no-marks-yet, and one realistic multi-panel case).
- meets that have been completed cannot have new routines created or existing
  routines updated (PATCH) or deleted (DELETE). This is enforced in the router,
  not the model, so it needs to be tested here.
"""

from decimal import Decimal

from app.models import Apparatus, Level, MeetStatus, Panel
from test.conftest import (
    make_gymnast,
    make_judge,
    make_judge_score,
    make_meet,
    make_meet_entry,
    make_routine,
)


def _entry(db_session, level=Level.level_3):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    return make_meet_entry(db_session, meet, gymnast=gymnast, level=level)


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


def test_create_routine_default_penalty_is_zero(client, db_session):
    entry = _entry(db_session)
    db_session.commit()

    response = client.post("/routines", json={"entry_id": entry.id, "apparatus": "ball"})

    assert response.status_code == 201
    assert Decimal(response.json()["penalty"]) == Decimal("0")


def test_create_routine_with_explicit_penalty(client, db_session):
    entry = _entry(db_session)
    db_session.commit()

    response = client.post(
        "/routines",
        json={"entry_id": entry.id, "apparatus": "ball", "penalty": "0.30"},
    )

    assert response.status_code == 201
    assert Decimal(response.json()["penalty"]) == Decimal("0.30")


def test_create_routine_negative_penalty_rejected(client, db_session):
    entry = _entry(db_session)
    db_session.commit()

    response = client.post(
        "/routines",
        json={"entry_id": entry.id, "apparatus": "ball", "penalty": "-0.10"},
    )
    assert response.status_code == 422


def test_create_routine_entry_not_found(client):
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


def test_create_routine_meet_completed_rejected(client, db_session):
    meet = make_meet(db_session, status=MeetStatus.completed)
    gymnast = make_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast=gymnast)
    db_session.commit()

    response = client.post(
        "/routines",
        json={"entry_id": entry.id, "apparatus": "hoop"},
    )
    assert response.status_code == 409
    assert MeetStatus.completed.value in response.json()["detail"].lower()


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


##-- GET /routines/{id}/score --##
def test_get_routine_score_not_found(client):
    response = client.get("/routines/9999/score")
    assert response.status_code == 404


def test_get_routine_score_no_marks_yet(client, db_session):
    entry = _entry(db_session)
    routine = make_routine(db_session, entry, apparatus=Apparatus.hoop)
    db_session.commit()

    response = client.get(f"/routines/{routine.id}/score")

    assert response.status_code == 200
    body = response.json()
    assert body["routine_id"] == routine.id
    assert Decimal(body["d_score"]) == Decimal("0.00")
    assert Decimal(body["a_score"]) == Decimal("0.00")
    assert Decimal(body["e_score"]) == Decimal("0.00")
    assert Decimal(body["penalty"]) == Decimal("0.00")
    assert Decimal(body["total"]) == Decimal("0.00")


def test_get_routine_score_composes_marks_and_penalty(client, db_session):
    # Explicit level-8+ band: this test exercises the full D/A/E panel, which the
    # default band-1-3 level (see _entry) no longer computes that way.
    entry = _entry(db_session, level=Level.senior)
    routine = make_routine(db_session, entry, apparatus=Apparatus.hoop)
    routine.penalty = Decimal("0.30")
    db_session.flush()
    db_session.commit()

    judge = make_judge(db_session)
    make_judge_score(
        db_session, routine=routine, judge=judge, panel=Panel.difficulty_body, value="3.30"
    )
    make_judge_score(
        db_session, routine=routine, judge=judge, panel=Panel.difficulty_apparatus, value="2.00"
    )
    make_judge_score(db_session, routine=routine, judge=judge, panel=Panel.artistry, value="9.00")
    make_judge_score(db_session, routine=routine, judge=judge, panel=Panel.execution, value="8.50")
    db_session.commit()

    response = client.get(f"/routines/{routine.id}/score")

    assert response.status_code == 200
    body = response.json()
    # d_score = difficulty_body (3.30) + difficulty_apparatus (2.00)
    assert Decimal(body["d_score"]) == Decimal("5.30")
    assert Decimal(body["a_score"]) == Decimal("9.00")
    assert Decimal(body["e_score"]) == Decimal("8.50")
    assert Decimal(body["penalty"]) == Decimal("0.30")
    assert Decimal(body["total"]) == Decimal("22.50")


def test_get_routine_score_final_score_for_level_1_3(client, db_session):
    # _entry defaults to Level.level_3, which is band 1-3: the single `final` mark IS
    # the routine's score, surfaced via final_score rather than the D/A/E panels.
    entry = _entry(db_session)
    routine = make_routine(db_session, entry, apparatus=Apparatus.hoop)
    db_session.commit()

    judge = make_judge(db_session)
    make_judge_score(db_session, routine=routine, judge=judge, panel=Panel.final, value="11.75")
    db_session.commit()

    response = client.get(f"/routines/{routine.id}/score")

    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["final_score"]) == Decimal("11.75")
    assert Decimal(body["total"]) == Decimal("11.75")


def test_get_routine_score_final_score_zero_for_level_8_plus(client, db_session):
    entry = _entry(db_session, level=Level.senior)
    routine = make_routine(db_session, entry, apparatus=Apparatus.hoop)
    db_session.commit()

    judge = make_judge(db_session)
    make_judge_score(db_session, routine=routine, judge=judge, panel=Panel.execution, value="9.00")
    db_session.commit()

    response = client.get(f"/routines/{routine.id}/score")

    assert response.status_code == 200
    assert response.json()["final_score"] == "0.00"


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


def test_update_routine_penalty(client, db_session):
    entry = _entry(db_session)
    routine = make_routine(db_session, entry, apparatus=Apparatus.rope)
    db_session.commit()

    response = client.patch(f"/routines/{routine.id}", json={"penalty": "0.50"})

    assert response.status_code == 200
    assert Decimal(response.json()["penalty"]) == Decimal("0.50")


def test_update_routine_penalty_negative_rejected(client, db_session):
    entry = _entry(db_session)
    routine = make_routine(db_session, entry, apparatus=Apparatus.rope)
    db_session.commit()

    response = client.patch(f"/routines/{routine.id}", json={"penalty": "-0.10"})
    assert response.status_code == 422


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


def test_update_routine_meet_completed_rejected(client, db_session):
    meet = make_meet(db_session, status=MeetStatus.completed)
    gymnast = make_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast=gymnast)
    routine = make_routine(db_session, entry, apparatus=Apparatus.hoop)
    db_session.commit()

    response = client.patch(f"/routines/{routine.id}", json={"order_of_performance": 1})
    assert response.status_code == 409
    assert MeetStatus.completed.value in response.json()["detail"].lower()


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


def test_delete_routine_meet_completed_rejected(client, db_session):
    meet = make_meet(db_session, status=MeetStatus.completed)
    gymnast = make_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast=gymnast)
    routine = make_routine(db_session, entry, apparatus=Apparatus.hoop)
    db_session.commit()

    response = client.delete(f"/routines/{routine.id}")
    assert response.status_code == 409
    assert MeetStatus.completed.value in response.json()["detail"].lower()
