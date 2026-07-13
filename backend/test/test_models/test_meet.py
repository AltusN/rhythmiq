"""
Tests the Meet model and its relationships

Covers:
 - Basic creation and persistence
 - Default status value
 - Date constraint (end_date >= start_date)
 - Status transitions
 - Cascade delete of entries and routines when a meet is deleted
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Apparatus, District, Meet, MeetEntry, MeetStatus, Routine
from test.conftest import make_district, make_gymnast, make_meet, make_meet_entry, make_routine


# Create a meet with valid data
def test_meet_create_with_required_fields(db_session):
    make_meet(db_session)
    db_session.commit()

    fetched = db_session.query(Meet).first()
    assert fetched is not None
    assert fetched.name == "Test Meet"
    assert fetched.location == "Test Location"
    assert fetched.start_date == date(2026, 6, 1)
    assert fetched.end_date == date(2026, 6, 2)
    assert fetched.status == MeetStatus.scheduled


def test_meet_can_be_national_with_no_district(db_session):
    meet = make_meet(db_session, district=None)
    db_session.commit()

    fetched = db_session.query(Meet).filter_by(id=meet.id).first()
    assert fetched is not None
    assert fetched.district_id is None
    assert fetched.district is None


def test_meet_can_belong_to_district(db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district=district)
    db_session.commit()

    fetched = db_session.query(Meet).filter_by(id=meet.id).first()
    assert fetched is not None
    assert fetched.district_id == district.id
    assert fetched.district is not None
    assert fetched.district.id == district.id


def test_meet_default_status_is_draft(db_session):
    meet = Meet(
        name="Draft Meet",
        location="Draft Location",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 2),
        # Leave out status intentionally to test default.
    )
    db_session.add(meet)
    db_session.commit()

    fetched = db_session.query(Meet).filter_by(name="Draft Meet").first()
    assert fetched is not None

    assert fetched.status == MeetStatus.draft


def test_meet_single_day_is_valid(db_session):
    make_meet(db_session, start_date=date(2026, 6, 1), end_date=date(2026, 6, 1))
    db_session.commit()

    fetched = db_session.query(Meet).filter_by(name="Test Meet").first()
    assert fetched is not None

    assert fetched.start_date == fetched.end_date


def test_meet_end_date_before_start_date_raises_error(db_session):
    meet = Meet(
        name="Invalid Meet",
        location="Invalid Location",
        start_date=date(2026, 6, 2),
        end_date=date(2026, 6, 1),
    )
    db_session.add(meet)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_meet_invalid_district_id_raises_error(db_session):
    meet = Meet(
        district_id=99999,
        name="Invalid District Meet",
        location="Invalid Location",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 2),
    )
    db_session.add(meet)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_meet_status_can_be_updated(db_session):
    meet = make_meet(db_session, status=MeetStatus.scheduled)
    db_session.commit()

    # Update status
    meet.status = MeetStatus.in_progress
    db_session.commit()
    db_session.refresh(meet)

    assert meet.status == MeetStatus.in_progress


def test_multiple_meets_can_be_updated(db_session):
    meet1 = make_meet(db_session, name="Meet 1", status=MeetStatus.scheduled)
    meet2 = make_meet(db_session, name="Meet 2", status=MeetStatus.scheduled)
    db_session.commit()

    # Update both meets
    meet1.status = MeetStatus.in_progress
    meet2.status = MeetStatus.cancelled
    db_session.commit()

    db_session.refresh(meet1)
    db_session.refresh(meet2)

    assert meet1.status == MeetStatus.in_progress
    assert meet2.status == MeetStatus.cancelled


def test_meet_cascade_delete(db_session):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast)
    routine = make_routine(db_session, entry)
    db_session.commit()

    db_session.delete(meet)
    db_session.commit()

    assert db_session.query(Meet).filter_by(id=meet.id).first() is None
    assert db_session.query(MeetEntry).filter_by(id=entry.id).first() is None
    assert db_session.query(Routine).filter_by(id=routine.id).first() is None


def test_meet_entry_routine_relationship(db_session):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast)
    make_routine(db_session, entry, apparatus=Apparatus.hoop)
    make_routine(db_session, entry, apparatus=Apparatus.ribbon)

    db_session.commit()

    fetched_entry = db_session.query(MeetEntry).first()
    # Routines is a list of routines associated with the entry
    assert len(fetched_entry.routines) == 2


def test_meet_medal_cutoffs_default_to_null(db_session):
    meet = make_meet(db_session)
    db_session.commit()

    fetched = db_session.query(Meet).filter_by(id=meet.id).first()
    assert fetched.medal_gold_min is None
    assert fetched.medal_silver_min is None


def test_meet_medal_cutoffs_can_be_set_together(db_session):
    meet = make_meet(db_session, medal_gold_min=Decimal("24.00"), medal_silver_min=Decimal("20.00"))
    db_session.commit()

    fetched = db_session.query(Meet).filter_by(id=meet.id).first()
    assert fetched.medal_gold_min == 24
    assert fetched.medal_silver_min == 20


def _unsaved_meet(**medal_kwargs) -> Meet:
    return Meet(
        name="Cutoff Meet",
        location="Test Location",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 2),
        **medal_kwargs,
    )


def test_meet_medal_cutoffs_gold_not_greater_than_silver_raises_error(db_session):
    # make_meet flushes internally, so it can't be used here -- the CheckConstraint
    # fires on INSERT (not deferred to COMMIT), and needs to happen inside pytest.raises.
    db_session.add(
        _unsaved_meet(medal_gold_min=Decimal("20.00"), medal_silver_min=Decimal("20.00"))
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_meet_medal_cutoffs_gold_only_raises_error(db_session):
    db_session.add(_unsaved_meet(medal_gold_min=Decimal("24.00"), medal_silver_min=None))

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_meet_medal_cutoffs_silver_only_raises_error(db_session):
    db_session.add(_unsaved_meet(medal_gold_min=None, medal_silver_min=Decimal("20.00")))

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_deleting_district_nulls_meet_district_id(db_session):
    district = make_district(db_session)
    meet = make_meet(db_session, district=district)
    db_session.commit()

    db_session.delete(district)
    db_session.commit()
    db_session.refresh(meet)

    assert db_session.query(District).filter_by(id=district.id).first() is None
    assert meet.district_id is None
