"""
Test suite for the judge score router.
- Post /judge_scores
-- Test creating a judge score with valid data
-- Test creating a judge score with invalid routine_id
-- Test creating a judge score with invalid judge_id
-- Test creating a judge score with duplicate routine_id, judge_id, and panel
-- Test creating a judge score with same routine_id/judge_id but a different panel (allowed)
-- Test creating a judge score with difficulty > 10
-- Test creating a judge score with execution > 10
-- Test creating a judge score after meet completion (should be rejected)
- Get /judge_scores
-- Test listing all judge scores
-- Test filtering judge scores by routine_id
-- Test filtering judge scores by judge_id
-- Test filtering judge scores by panel
- Get /judge_scores/{judge_score_id}
-- Test retrieving a judge score by ID
-- Test retrieving a judge score with invalid ID
- Patch /judge_scores/{judge_score_id}
-- Test updating a judge score with valid data
-- Test updating a judge score with invalid data
-- Test updating a judge score with invalid ID
-- Test updating a judge score after meet completion (should be rejected)
-Delete /judge_scores/{judge_score_id}
-- Test deleting a judge score by ID
-- Test deleting a judge score with invalid ID
-- Test deleting a judge score after meet completion (should be rejected)
"""

from decimal import Decimal

from app.models import Apparatus, Level, MeetStatus, Panel
from test.conftest import (
    make_club,
    make_district,
    make_gymnast,
    make_judge,
    make_meet,
    make_meet_entry,
    make_routine,
)


def _make_judge_routine(db_session):
    """
    Helper function that creates a judge and a routine, plus exposes the routine's
    meet_entry so callers can build a second routine for the same gymnast on a
    different apparatus (rather than getting a brand-new gymnast from make_routine's
    auto-build path). Returns a (routine, judge, meet_entry) tuple.

    Uses Level.senior (rather than make_meet_entry's level_3 default, which under the
    band table only accepts Panel.final) so these tests keep exercising panel/value
    semantics across all four D/A/E panels -- level-gating itself is tested separately
    below.
    """
    district = make_district(db_session)
    club = make_club(db_session, district=district)
    gymnast = make_gymnast(db_session, club=club)
    meet = make_meet(db_session, district=district)
    meet_entry = make_meet_entry(db_session, meet=meet, gymnast=gymnast, level=Level.senior)
    routine = make_routine(db_session, meet_entry=meet_entry)
    judge = make_judge(db_session)

    return routine, judge, meet_entry


def test_create_judge_score(client, db_session):
    # Test creating a judge score with valid data
    routine, judge, _ = _make_judge_routine(db_session)

    payload = {
        "routine_id": routine.id,
        "judge_id": judge.id,
        "panel": Panel.artistry,
        "value": 9.5,
    }
    response = client.post("/judge-scores/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["routine_id"] == payload["routine_id"]
    assert data["judge_id"] == payload["judge_id"]
    assert data["panel"] == payload["panel"]
    assert Decimal(data["value"]) == Decimal(str(payload["value"]))


def test_create_judge_score_invalid_routine(client, db_session):
    # Test creating a judge score with invalid routine_id
    _, judge, _ = _make_judge_routine(db_session)

    payload = {
        "routine_id": 9999,  # Non-existent routine_id
        "judge_id": judge.id,
        "panel": Panel.execution,
        "value": 8.5,
    }
    response = client.post("/judge-scores/", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert "Routine with id" in data["detail"]


def test_create_judge_score_invalid_judge(client, db_session):
    # Test creating a judge score with invalid judge_id
    routine, _, _ = _make_judge_routine(db_session)

    payload = {
        "routine_id": routine.id,
        "judge_id": 9999,  # Non-existent judge_id
        "panel": Panel.execution,
        "value": 8.5,
    }
    response = client.post("/judge-scores/", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert "Judge with id" in data["detail"]


def test_create_judge_score_duplicate(client, db_session):
    # Test creating a judge score with duplicate routine_id, judge_id, and panel
    routine, judge, _ = _make_judge_routine(db_session)

    payload = {
        "routine_id": routine.id,
        "judge_id": judge.id,
        "panel": Panel.execution,
        "value": 8.5,
    }
    # Create the first judge score
    response1 = client.post("/judge-scores/", json=payload)
    assert response1.status_code == 201

    # Attempt to create a duplicate judge score
    response2 = client.post("/judge-scores/", json=payload)
    assert response2.status_code == 409
    data = response2.json()
    assert "has already submitted" in data["detail"]


def test_create_judge_score_same_routine_and_judge_different_panel_allowed(client, db_session):
    # Uniqueness is scoped to (routine_id, judge_id, panel) together, not just
    # (routine_id, judge_id) -- the same judge scoring the same routine on a
    # different panel is a normal, expected case (e.g. artistry then execution).
    routine, judge, _ = _make_judge_routine(db_session)

    payload_1 = {
        "routine_id": routine.id,
        "judge_id": judge.id,
        "panel": Panel.execution,
        "value": 8.5,
    }
    payload_2 = {
        "routine_id": routine.id,
        "judge_id": judge.id,
        "panel": Panel.artistry,
        "value": 9.0,
    }
    response1 = client.post("/judge-scores/", json=payload_1)
    assert response1.status_code == 201

    response2 = client.post("/judge-scores/", json=payload_2)
    assert response2.status_code == 201


def test_create_judge_score_difficulty_gt_10(client, db_session):
    # Test creating a judge score with difficulty > 10
    routine, judge, _ = _make_judge_routine(db_session)

    payload = {
        "routine_id": routine.id,
        "judge_id": judge.id,
        "panel": Panel.difficulty_apparatus,
        "value": 10.5,  # > 10 allowed
    }
    response = client.post("/judge-scores/", json=payload)
    assert response.status_code == 201  # Created


def test_create_judge_score_execution_gt_10(client, db_session):
    # Test creating a judge score with execution > 10
    routine, judge, _ = _make_judge_routine(db_session)

    payload = {
        "routine_id": routine.id,
        "judge_id": judge.id,
        "panel": Panel.execution,
        "value": 10.5,  # > 10 not allowed
    }
    response = client.post("/judge-scores/", json=payload)
    assert response.status_code == 422  # Unprocessable Entity


def test_create_judge_score_artistry_gt_10(client, db_session):
    # Test creating a judge score with artistry > 10
    routine, judge, _ = _make_judge_routine(db_session)

    payload = {
        "routine_id": routine.id,
        "judge_id": judge.id,
        "panel": Panel.artistry,
        "value": 10.5,  # > 10 not allowed
    }
    response = client.post("/judge-scores/", json=payload)
    assert response.status_code == 422  # Unprocessable Entity


def _make_level_1_routine(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district)
    gymnast = make_gymnast(db_session, club=club)
    meet = make_meet(db_session, district=district)
    meet_entry = make_meet_entry(db_session, meet=meet, gymnast=gymnast, level=Level.level_1)
    return make_routine(db_session, meet_entry=meet_entry)


def test_create_judge_score_difficulty_rejected_for_level_1(client, db_session):
    # level_1 routines are scored on Panel.final only (one pre-aggregated mark) -- a
    # difficulty_body mark is invalid for the routine's level, not just a data
    # conflict, hence 422.
    routine = _make_level_1_routine(db_session)
    judge = make_judge(db_session)

    payload = {
        "routine_id": routine.id,
        "judge_id": judge.id,
        "panel": Panel.difficulty_body,
        "value": 3.30,
    }
    response = client.post("/judge-scores/", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "final" in data["detail"]


def test_create_judge_score_artistry_rejected_for_level_1(client, db_session):
    routine = _make_level_1_routine(db_session)
    judge = make_judge(db_session)

    payload = {
        "routine_id": routine.id,
        "judge_id": judge.id,
        "panel": Panel.artistry,
        "value": 9.0,
    }
    response = client.post("/judge-scores/", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "final" in data["detail"]


def test_create_judge_score_execution_rejected_for_level_1(client, db_session):
    # Under the old E_ONLY_LEVELS rule, execution was the one valid panel at level 1.
    # Under the new band table, levels 1-3 record ONE pre-aggregated mark on
    # Panel.final instead -- execution is no longer valid there.
    routine = _make_level_1_routine(db_session)
    judge = make_judge(db_session)

    payload = {
        "routine_id": routine.id,
        "judge_id": judge.id,
        "panel": Panel.execution,
        "value": 8.5,
    }
    response = client.post("/judge-scores/", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "final" in data["detail"]


def test_create_judge_score_final_allowed_for_level_1(client, db_session):
    # The one panel that IS valid for a level 1-3 routine should not be blocked by the gate.
    routine = _make_level_1_routine(db_session)
    judge = make_judge(db_session)

    payload = {
        "routine_id": routine.id,
        "judge_id": judge.id,
        "panel": Panel.final,
        "value": 11.50,
    }
    response = client.post("/judge-scores/", json=payload)
    assert response.status_code == 201


def test_create_judge_score_after_meet_completion_rejected(client, db_session):
    # Test creating a judge score after the meet has been marked as completed
    routine, judge, _ = _make_judge_routine(db_session)
    routine.entry.meet.status = MeetStatus.completed  # Mark the meet as completed
    db_session.commit()

    payload = {
        "routine_id": routine.id,
        "judge_id": judge.id,
        "panel": Panel.execution,
        "value": 8.5,
    }
    response = client.post("/judge-scores/", json=payload)
    assert response.status_code == 409  # Conflict
    data = response.json()
    assert f"Meet {routine.entry.meet.id} is completed" in data["detail"]


def test_get_empty_judge_scores(client):
    # Test listing judge scores when none exist
    response = client.get("/judge-scores/")
    assert response.status_code == 200
    data = response.json()
    assert data == []  # Should return an empty list


def test_get_all_judge_scores(client, db_session):
    # Test listing all judge scores
    routine, judge, meet_entry = _make_judge_routine(db_session)
    db_session.commit()  # Commit to ensure IDs are generated
    routine_2 = make_routine(db_session, meet_entry=meet_entry, apparatus=Apparatus.ball)

    payload_1 = {
        "routine_id": routine.id,
        "judge_id": judge.id,
        "panel": Panel.artistry,
        "value": 9.0,
    }
    payload_2 = {
        "routine_id": routine_2.id,
        "judge_id": judge.id,
        "panel": Panel.execution,
        "value": 8.5,
    }
    # Create two judge scores
    client.post("/judge-scores/", json=payload_1)
    client.post("/judge-scores/", json=payload_2)

    response = client.get("/judge-scores/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # Both judge scores exist


def test_get_judge_scores_by_routine(client, db_session):
    # Test filtering judge scores by routine_id
    routine, judge, _ = _make_judge_routine(db_session)
    db_session.commit()  # Commit to ensure IDs are generated

    payload = {
        "routine_id": routine.id,
        "judge_id": judge.id,
        "panel": Panel.execution,
        "value": 8.5,
    }
    # Create a judge score
    client.post("/judge-scores/", json=payload)

    response = client.get(f"/judge-scores/?routine_id={routine.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1  # the filter actually matched something
    assert all(score["routine_id"] == routine.id for score in data)


def test_get_judge_scores_by_judge(client, db_session):
    # Test filtering judge scores by judge_id
    _, judge, meet_entry = _make_judge_routine(db_session)
    db_session.commit()  # Commit to ensure IDs are generated
    routine_2 = make_routine(db_session, meet_entry=meet_entry, apparatus=Apparatus.ball)

    payload = {
        "routine_id": routine_2.id,
        "judge_id": judge.id,
        "panel": Panel.artistry,
        "value": 8.5,
    }
    # Create a judge score
    client.post("/judge-scores/", json=payload)

    response = client.get(f"/judge-scores/?judge_id={judge.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1  # the filter actually matched something
    assert all(score["judge_id"] == judge.id for score in data)


def test_get_judge_scores_by_panel(client, db_session):
    # Test filtering judge scores by panel
    routine, judge, _ = _make_judge_routine(db_session)
    db_session.commit()  # Commit to ensure IDs are generated

    payload = {
        "routine_id": routine.id,
        "judge_id": judge.id,
        "panel": Panel.execution,
        "value": 8.5,
    }
    # Create a judge score
    client.post("/judge-scores/", json=payload)

    response = client.get(f"/judge-scores/?panel={Panel.execution}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1  # the filter actually matched something
    assert all(score["panel"] == Panel.execution for score in data)


def test_get_judge_scores_by_id(client, db_session):
    # Test retrieving a judge score by ID
    routine, judge, _ = _make_judge_routine(db_session)
    db_session.commit()  # Commit to ensure IDs are generated

    payload = {
        "routine_id": routine.id,
        "judge_id": judge.id,
        "panel": Panel.execution,
        "value": 8.5,
    }
    # Create a judge score
    response_create = client.post("/judge-scores/", json=payload)
    assert response_create.status_code == 201
    created_score = response_create.json()
    judge_score_id = created_score["id"]

    # Retrieve the judge score by ID
    response_get = client.get(f"/judge-scores/{judge_score_id}")
    assert response_get.status_code == 200
    retrieved_score = response_get.json()
    assert retrieved_score["id"] == judge_score_id


def test_get_judge_score_invalid_id(client):
    # Test retrieving a judge score with invalid ID
    response = client.get("/judge-scores/9999")  # Non-existent ID
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"]


##-- Patch --##
def test_update_judge_score_success(client, db_session):
    # Test updating a judge score's value
    routine, judge, _ = _make_judge_routine(db_session)
    db_session.commit()  # Commit to ensure IDs are generated

    payload = {
        "routine_id": routine.id,
        "judge_id": judge.id,
        "panel": Panel.execution,
        "value": 8.5,
    }
    response_create = client.post("/judge-scores/", json=payload)
    assert response_create.status_code == 201
    judge_score_id = response_create.json()["id"]

    response_update = client.patch(f"/judge-scores/{judge_score_id}", json={"value": 9.0})
    assert response_update.status_code == 200
    data = response_update.json()
    assert Decimal(data["value"]) == Decimal("9.0")
    # routine_id/judge_id/panel are identity fields -- not touched by the update
    assert data["routine_id"] == routine.id
    assert data["judge_id"] == judge.id
    assert data["panel"] == Panel.execution


def test_update_judge_score_capped_panel_over_10_rejected(client, db_session):
    # Raising an existing artistry/execution score above 10.0 has no panel field in
    # JudgeScoreUpdate to validate against in Pydantic, so this is only caught by the
    # ck_judge_score_panel_value_cap DB constraint -- the one constraint only reachable
    # through PATCH, not POST.
    routine, judge, _ = _make_judge_routine(db_session)
    db_session.commit()  # Commit to ensure IDs are generated

    payload = {
        "routine_id": routine.id,
        "judge_id": judge.id,
        "panel": Panel.artistry,
        "value": 9.0,
    }
    response_create = client.post("/judge-scores/", json=payload)
    assert response_create.status_code == 201
    judge_score_id = response_create.json()["id"]

    response_update = client.patch(f"/judge-scores/{judge_score_id}", json={"value": 10.5})
    assert response_update.status_code == 409
    data = response_update.json()
    assert "cannot exceed 10.0" in data["detail"]


def test_update_judge_score_invalid_id(client):
    # Test updating a judge score with invalid ID
    response = client.patch("/judge-scores/9999", json={"value": 9.0})
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"]


def test_update_judge_score_after_meet_completion_rejected(client, db_session):
    # Test updating a judge score after the meet has been marked as completed
    routine, judge, _ = _make_judge_routine(db_session)
    db_session.commit()  # Commit to ensure IDs are generated

    payload = {
        "routine_id": routine.id,
        "judge_id": judge.id,
        "panel": Panel.execution,
        "value": 8.5,
    }
    response_create = client.post("/judge-scores/", json=payload)
    assert response_create.status_code == 201
    judge_score_id = response_create.json()["id"]

    # Mark the meet as completed
    routine.entry.meet.status = MeetStatus.completed
    db_session.commit()

    # Attempt to update the judge score after meet completion
    response_update = client.patch(f"/judge-scores/{judge_score_id}", json={"value": 9.0})
    assert response_update.status_code == 409  # Conflict
    data = response_update.json()
    assert f"Meet {routine.entry.meet.id} is completed" in data["detail"]


##-- Delete --##
def test_delete_judge_score(client, db_session):
    # Test deleting a judge score by ID
    routine, judge, _ = _make_judge_routine(db_session)
    db_session.commit()  # Commit to ensure IDs are generated

    payload = {
        "routine_id": routine.id,
        "judge_id": judge.id,
        "panel": Panel.execution,
        "value": 8.5,
    }
    # Create a judge score
    response_create = client.post("/judge-scores/", json=payload)
    assert response_create.status_code == 201
    created_score = response_create.json()
    judge_score_id = created_score["id"]

    # Delete the judge score by ID
    response_delete = client.delete(f"/judge-scores/{judge_score_id}")
    assert response_delete.status_code == 204  # No Content

    # Verify that the judge score no longer exists
    response_get = client.get(f"/judge-scores/{judge_score_id}")
    assert response_get.status_code == 404
    data = response_get.json()
    assert "not found" in data["detail"]


def test_delete_judge_score_invalid_id(client):
    # Test deleting a judge score with invalid ID
    response = client.delete("/judge-scores/9999")  # Non-existent ID
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"]


def test_delete_judge_score_after_meet_completion_rejected(client, db_session):
    # Test deleting a judge score after the meet has been marked as completed
    routine, judge, _ = _make_judge_routine(db_session)
    db_session.commit()  # Commit to ensure IDs are generated

    payload = {
        "routine_id": routine.id,
        "judge_id": judge.id,
        "panel": Panel.execution,
        "value": 8.5,
    }
    response_create = client.post("/judge-scores/", json=payload)
    assert response_create.status_code == 201
    judge_score_id = response_create.json()["id"]

    # Mark the meet as completed
    routine.entry.meet.status = MeetStatus.completed
    db_session.commit()

    # Attempt to delete the judge score after meet completion
    response_delete = client.delete(f"/judge-scores/{judge_score_id}")
    assert response_delete.status_code == 409  # Conflict
    data = response_delete.json()
    assert f"Meet {routine.entry.meet.id} is completed" in data["detail"]


##-- Level-band panel gate (app.scoring.profile_for_level) --##
# Note: level-1 execution-rejected and final-allowed are covered above by
# test_create_judge_score_execution_rejected_for_level_1 /
# test_create_judge_score_final_allowed_for_level_1 (which use the _make_level_1_routine
# helper); the remaining band-gate cases below cover levels 4 and 8.


def test_create_judge_score_accepts_difficulty_body_at_level_4(client, db_session):
    # The headline spec change: the backend used to REJECT a Difficulty mark at level 4.
    entry = make_meet_entry(
        db_session,
        meet=make_meet(db_session),
        gymnast=make_gymnast(db_session),
        level=Level.level_4,
    )
    routine = make_routine(db_session, meet_entry=entry)
    judge = make_judge(db_session)
    db_session.commit()

    response = client.post(
        "/judge-scores/",
        json={
            "routine_id": routine.id,
            "judge_id": judge.id,
            "panel": "difficulty_body",
            "value": "2.40",
        },
    )

    assert response.status_code == 201


def test_create_judge_score_rejects_artistry_at_level_4(client, db_session):
    entry = make_meet_entry(
        db_session,
        meet=make_meet(db_session),
        gymnast=make_gymnast(db_session),
        level=Level.level_4,
    )
    routine = make_routine(db_session, meet_entry=entry)
    judge = make_judge(db_session)
    db_session.commit()

    response = client.post(
        "/judge-scores/",
        json={
            "routine_id": routine.id,
            "judge_id": judge.id,
            "panel": "artistry",
            "value": "8.00",
        },
    )

    assert response.status_code == 422


def test_create_judge_score_rejects_final_at_level_8(client, db_session):
    entry = make_meet_entry(
        db_session,
        meet=make_meet(db_session),
        gymnast=make_gymnast(db_session),
        level=Level.level_8,
    )
    routine = make_routine(db_session, meet_entry=entry)
    judge = make_judge(db_session)
    db_session.commit()

    response = client.post(
        "/judge-scores/",
        json={
            "routine_id": routine.id,
            "judge_id": judge.id,
            "panel": "final",
            "value": "12.00",
        },
    )

    assert response.status_code == 422
