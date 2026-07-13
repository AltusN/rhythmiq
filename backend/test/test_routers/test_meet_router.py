"""
Test suite for the meet router.
- district_id is optional (national meets have none), pre-checked for existence when
  present.
- Date validation: start_date <= end_date on create; on PATCH, the model_validator only
  fires when both dates are sent together, otherwise the router validates the incoming
  date against the stored counterpart.
- status transitions are forward-only (draft -> scheduled -> in_progress -> completed),
  any status can go to cancelled, and sending the current status is a no-op.
- DELETE is rejected (409) while status is in_progress or completed.
- medal_gold_min/medal_silver_min: both-or-neither + gold > silver, validated the
  same way as dates -- full-payload case in the schema, partial (one field sent)
  case in the router against the stored counterpart.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.models import MeetStatus
from test.conftest import make_district, make_meet


##-- Post /meets/ --##
def test_create_meet_success(client, db_session):
    district = make_district(db_session)

    meet_data = {
        "name": "South Circle",
        "start_date": date(2026, 6, 1).isoformat(),
        "end_date": date(2026, 6, 3).isoformat(),
        "district_id": district.id,
        "location": "Somerset West",
    }

    response = client.post("/meets/", json=meet_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == meet_data["name"]
    assert data["start_date"] == meet_data["start_date"]
    assert data["end_date"] == meet_data["end_date"]
    assert data["district_id"] == meet_data["district_id"]


def test_creat_meet_create_national_meet_success(client, db_session):
    meet_data = {
        "name": "South Circle",
        "start_date": date(2026, 6, 1).isoformat(),
        "end_date": date(2026, 6, 3).isoformat(),
        "location": "Somerset West",
    }

    response = client.post("/meets/", json=meet_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == meet_data["name"]
    assert data["start_date"] == meet_data["start_date"]
    assert data["end_date"] == meet_data["end_date"]
    assert data["district_id"] is None


def test_create_meet_fail_invalid_dates(client, db_session):
    district = make_district(db_session)

    meet_data = {
        "name": "South Circle",
        "start_date": date(2026, 6, 3).isoformat(),
        "end_date": date(2026, 6, 1).isoformat(),
        "district_id": district.id,
        "location": "Somerset West",
    }

    response = client.post("/meets/", json=meet_data)
    assert response.status_code == 422


def test_create_meet_district_id_not_found(client, db_session):
    meet_data = {
        "name": "South Circle",
        "start_date": date(2026, 6, 1).isoformat(),
        "end_date": date(2026, 6, 3).isoformat(),
        "district_id": 9999,
        "location": "Somerset West",
    }

    response = client.post("/meets/", json=meet_data)
    assert response.status_code == 404
    response.json()


def test_create_meet_same_start_and_end_date(client, db_session):
    district = make_district(db_session)

    meet_data = {
        "name": "South Circle",
        "start_date": date(2026, 6, 1).isoformat(),
        "end_date": date(2026, 6, 1).isoformat(),
        "district_id": district.id,
        "location": "Somerset West",
    }

    response = client.post("/meets/", json=meet_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == meet_data["name"]
    assert data["start_date"] == meet_data["start_date"]
    assert data["end_date"] == meet_data["end_date"]
    assert data["district_id"] == meet_data["district_id"]


def test_create_meet_explicit_invalid_status(client, db_session):
    district = make_district(db_session)

    meet_data = {
        "name": "South Circle",
        "start_date": date(2026, 6, 1).isoformat(),
        "end_date": date(2026, 6, 3).isoformat(),
        "district_id": district.id,
        "location": "Somerset West",
        "status": "published",
    }

    response = client.post("/meets/", json=meet_data)
    assert response.status_code == 422


def test_create_meet_whitespace_in_name_and_location(client, db_session):
    district = make_district(db_session)

    meet_data = {
        "name": "  South Circle  ",
        "start_date": date(2026, 6, 1).isoformat(),
        "end_date": date(2026, 6, 3).isoformat(),
        "district_id": district.id,
        "location": "  Somerset West  ",
    }

    response = client.post("/meets/", json=meet_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == meet_data["name"].strip()
    assert data["location"] == meet_data["location"].strip()


def test_create_meet_with_explicit_status(client, db_session):
    district = make_district(db_session)

    meet_data = {
        "name": "South Circle",
        "start_date": date(2026, 6, 1).isoformat(),
        "end_date": date(2026, 6, 3).isoformat(),
        "district_id": district.id,
        "location": "Somerset West",
        "status": "scheduled",
    }

    response = client.post("/meets/", json=meet_data)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == meet_data["status"]


def test_create_meet_with_medal_cutoffs(client, db_session):
    district = make_district(db_session)

    meet_data = {
        "name": "Club Invitational",
        "start_date": date(2026, 6, 1).isoformat(),
        "end_date": date(2026, 6, 3).isoformat(),
        "district_id": district.id,
        "location": "Somerset West",
        "medal_gold_min": "24.00",
        "medal_silver_min": "20.00",
    }

    response = client.post("/meets/", json=meet_data)
    assert response.status_code == 201
    data = response.json()
    assert data["medal_gold_min"] == "24.00"
    assert data["medal_silver_min"] == "20.00"


def test_create_meet_medal_cutoffs_gold_only_rejected(client, db_session):
    meet_data = {
        "name": "Club Invitational",
        "start_date": date(2026, 6, 1).isoformat(),
        "end_date": date(2026, 6, 3).isoformat(),
        "location": "Somerset West",
        "medal_gold_min": "24.00",
    }

    response = client.post("/meets/", json=meet_data)
    assert response.status_code == 422


##-- Get /meets/{meet_id} --##
def test_get_meet_success(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district)

    response = client.get(f"/meets/{meet.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == meet.id
    assert data["name"] == meet.name
    assert data["district_id"] == meet.district_id


def test_get_meet_not_found(client, db_session):
    response = client.get("/meets/9999")
    assert response.status_code == 404


def test_get_all_meets(client, db_session):
    district = make_district(db_session)
    meet1 = make_meet(db_session, district, name="Meet 1")
    meet2 = make_meet(db_session, district, name="Meet 2")
    meet3 = make_meet(db_session)

    response = client.get("/meets")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    meet_ids = [meet["id"] for meet in data]
    assert meet1.id in meet_ids
    assert meet2.id in meet_ids
    assert meet3.id in meet_ids


def test_get_all_meets_empty(client, db_session):
    response = client.get("/meets/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0


##-- Patch /meets/{meet_id} --##
def test_update_meet_success(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district)

    update_data = {
        "name": "Updated Meet Name",
        "location": "Updated Location",
        "start_date": date(2026, 7, 1).isoformat(),
        "end_date": date(2026, 7, 3).isoformat(),
        "status": MeetStatus.scheduled,
    }

    response = client.patch(f"/meets/{meet.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == meet.id
    assert data["name"] == update_data["name"]
    assert data["location"] == update_data["location"]
    assert data["start_date"] == update_data["start_date"]
    assert data["end_date"] == update_data["end_date"]
    assert data["status"] == update_data["status"]


def test_update_start_date_only_valid(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district)

    update_data = {"start_date": date(2026, 6, 2).isoformat()}

    response = client.patch(f"/meets/{meet.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == meet.id
    assert data["start_date"] == update_data["start_date"]
    assert data["end_date"] == meet.end_date.isoformat()  # Ensure end_date remains unchanged


def test_update_end_date_only_valid(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district)

    update_data = {"end_date": date(2026, 7, 3).isoformat()}

    response = client.patch(f"/meets/{meet.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == meet.id
    assert data["end_date"] == update_data["end_date"]
    assert data["start_date"] == meet.start_date.isoformat()  # Ensure start_date remains unchanged


def test_update_meet_start_date_invalid(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district)

    update_data = {
        "start_date": date(2026, 7, 5).isoformat(),
        "end_date": date(2026, 7, 3).isoformat(),
    }

    response = client.patch(f"/meets/{meet.id}", json=update_data)
    assert response.status_code == 422


def test_update_meet_end_date_invalid(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district)

    update_data = {
        "start_date": date(2026, 7, 5).isoformat(),
        "end_date": date(2026, 7, 3).isoformat(),
    }

    response = client.patch(f"/meets/{meet.id}", json=update_data)
    assert response.status_code == 422


def test_update_meet_medal_cutoffs_together(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district)

    update_data = {"medal_gold_min": "24.00", "medal_silver_min": "20.00"}

    response = client.patch(f"/meets/{meet.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["medal_gold_min"] == "24.00"
    assert data["medal_silver_min"] == "20.00"


def test_update_meet_medal_gold_only_valid_against_stored_silver(client, db_session):
    district = make_district(db_session)
    meet = make_meet(
        db_session, district, medal_gold_min=Decimal("24.00"), medal_silver_min=Decimal("20.00")
    )

    # Raising just the gold cutoff, leaving the stored silver_min (20.00) in place.
    response = client.patch(f"/meets/{meet.id}", json={"medal_gold_min": "26.00"})
    assert response.status_code == 200
    assert response.json()["medal_gold_min"] == "26.00"
    assert response.json()["medal_silver_min"] == "20.00"


def test_update_meet_medal_gold_only_invalid_against_stored_silver(client, db_session):
    district = make_district(db_session)
    meet = make_meet(
        db_session, district, medal_gold_min=Decimal("24.00"), medal_silver_min=Decimal("20.00")
    )

    # New gold_min would no longer be greater than the stored silver_min.
    response = client.patch(f"/meets/{meet.id}", json={"medal_gold_min": "18.00"})
    assert response.status_code == 422


def test_update_meet_medal_gold_only_rejected_when_no_cutoffs_stored(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district)  # no cutoffs configured

    response = client.patch(f"/meets/{meet.id}", json={"medal_gold_min": "24.00"})
    assert response.status_code == 422


def test_update_meet_district_to_none(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district)

    update_data = {"district_id": None}

    response = client.patch(f"/meets/{meet.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == meet.id
    assert data["district_id"] is None


def test_update_meet_not_found(client, db_session):
    update_data = {
        "name": "Updated Meet Name",
        "location": "Updated Location",
        "start_date": date(2026, 7, 1).isoformat(),
        "end_date": date(2026, 7, 3).isoformat(),
        "status": "completed",
    }

    response = client.patch("/meets/9999", json=update_data)
    assert response.status_code == 404


def tess_update_meet_body_is_empty_noop(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district)

    update_data = {}

    response = client.patch(f"/meets/{meet.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == meet.id
    assert data["name"] == meet.name
    assert data["location"] == meet.location
    assert data["start_date"] == meet.start_date.isoformat()
    assert data["end_date"] == meet.end_date.isoformat()
    assert data["status"] == meet.status


##-- Status transition tests --##
def test_update_meet_status_draft_to_scheduled(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district, status=MeetStatus.draft)

    # Transition from draft to scheduled
    update_data = {"status": "scheduled"}
    response = client.patch(f"/meets/{meet.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == MeetStatus.scheduled


def test_update_meet_status_scheduled_to_in_progress(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district, status=MeetStatus.scheduled)

    # Transition from scheduled to in_progress
    update_data = {"status": "in_progress"}
    response = client.patch(f"/meets/{meet.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == MeetStatus.in_progress


def test_update_meet_status_in_progress_to_completed(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district, status=MeetStatus.in_progress)

    # Transition from in_progress to completed
    update_data = {"status": "completed"}
    response = client.patch(f"/meets/{meet.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == MeetStatus.completed


@pytest.mark.parametrize(
    "initial_status",
    [
        MeetStatus.draft,
        MeetStatus.scheduled,
        MeetStatus.in_progress,
    ],
)
def test_update_meet_status_any_to_canceled(client, db_session, initial_status):
    district = make_district(db_session)
    meet = make_meet(db_session, district, status=initial_status)

    # Transition from any status to canceled
    update_data = {"status": MeetStatus.cancelled}
    response = client.patch(f"/meets/{meet.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == MeetStatus.cancelled


def test_update_meet_backward_transition_blocked(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district, status=MeetStatus.completed)

    # Attempt to transition from completed back to in_progress
    update_data = {"status": "in_progress"}
    response = client.patch(f"/meets/{meet.id}", json=update_data)
    assert response.status_code == 409


def test_update_meet_invalid_status_value(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district, status=MeetStatus.draft)

    # Attempt to set an invalid status value
    update_data = {"status": "invalid_status"}
    response = client.patch(f"/meets/{meet.id}", json=update_data)
    assert response.status_code == 422


def test_update_meet_transition_skip_forwared_not_allowed(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district, status=MeetStatus.draft)

    # Attempt to transition from draft directly to completed
    update_data = {"status": "completed"}
    response = client.patch(f"/meets/{meet.id}", json=update_data)
    assert response.status_code == 409


def test_update_meet_no_change_allowed(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district, status=MeetStatus.scheduled)

    # Attempt to update the meet with the same status
    update_data = {"status": "scheduled"}
    response = client.patch(f"/meets/{meet.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == MeetStatus.scheduled


##-- Delete /meets/{meet_id} --##
def test_delete_meet_success(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district)

    response = client.delete(f"/meets/{meet.id}")
    assert response.status_code == 204

    # Verify that the meet is actually deleted
    get_response = client.get(f"/meets/{meet.id}")
    assert get_response.status_code == 404


def test_delete_meet_not_found(client, db_session):
    response = client.delete("/meets/9999")
    assert response.status_code == 404


def test_delete_meet_prevent_delete_in_progress(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district, status=MeetStatus.in_progress)

    response = client.delete(f"/meets/{meet.id}")
    assert response.status_code == 409


def test_delete_meet_prevent_delete_completed(client, db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district, status=MeetStatus.completed)

    response = client.delete(f"/meets/{meet.id}")
    assert response.status_code == 409
