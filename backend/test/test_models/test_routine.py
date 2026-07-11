"""
Tests for the Routine model, including:
- Creation with required fields; order_of_performance is optional
- All Apparatus enum values are valid
- uq_entry_apparatus: one row per apparatus per entry, but the same apparatus is fine
  across different entries, and multiple apparatuses are fine per entry
- entry/gymnast/group relationships and properties
- Cascade delete from MeetEntry
- music_url resolves live from the matching RoutineProfile (by gymnast/group +
  apparatus + level), and is None when no matching profile exists
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Apparatus, Level, MeetEntry, Routine
from test.conftest import (
    make_club,
    make_district,
    make_group,
    make_gymnast,
    make_meet,
    make_meet_entry,
    make_routine,
    make_routine_profile,
)


def test_routine_create_with_required_fields(db_session):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast)

    make_routine(db_session, entry)

    db_session.commit()

    fetched = db_session.query(Routine).first()
    assert fetched is not None
    assert fetched.entry_id == entry.id
    assert fetched.apparatus == Apparatus.freehand
    assert fetched.order_of_performance == 1


def test_routine_order_of_performance_optional(db_session):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast)

    routine = Routine(
        entry_id=entry.id,
        apparatus=Apparatus.ribbon,
        order_of_performance=None,
    )
    db_session.add(routine)
    db_session.commit()

    fetched = db_session.query(Routine).first()
    assert fetched is not None
    assert fetched.order_of_performance is None


def rest_routine_apparatus_not_null(db_session):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast)

    routine = Routine(
        entry_id=entry.id,
        apparatus=None,
        order_of_performance=1,
    )
    db_session.add(routine)

    with pytest.raises(IntegrityError):
        db_session.commit()


# == Apparatus enum ==#
@pytest.mark.parametrize("apparatus", list(Apparatus))
def test_routine_valid_apparatus_values(db_session, apparatus):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast)

    routine = Routine(
        entry_id=entry.id,
        apparatus=apparatus,
        order_of_performance=1,
    )
    db_session.add(routine)
    db_session.commit()

    fetched = db_session.query(Routine).first()
    assert fetched is not None
    assert fetched.apparatus == apparatus


def test_same_apparatus_different_entries(db_session):
    meet = make_meet(db_session)
    gymnast1 = make_gymnast(db_session, first_name="Alice", last_name="Smith")
    gymnast2 = make_gymnast(db_session, first_name="Bob", last_name="Johnson")
    entry1 = make_meet_entry(db_session, meet, gymnast1)
    entry2 = make_meet_entry(db_session, meet, gymnast2)

    make_routine(db_session, entry1, apparatus=Apparatus.hoop)
    make_routine(db_session, entry2, apparatus=Apparatus.hoop)

    db_session.commit()

    fetched_routines = db_session.query(Routine).all()
    assert len(fetched_routines) == 2
    assert fetched_routines[0].apparatus == Apparatus.hoop
    assert fetched_routines[1].apparatus == Apparatus.hoop


# == Multiple routines per entry ==#
def test_multiple_routines_per_entry(db_session):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast)

    make_routine(db_session, entry, apparatus=Apparatus.ball, order_of_performance=1)
    make_routine(db_session, entry, apparatus=Apparatus.clubs, order_of_performance=2)

    db_session.commit()

    fetched_routines = db_session.query(Routine).filter_by(entry_id=entry.id).all()
    assert len(fetched_routines) == 2
    assert fetched_routines[0].apparatus == Apparatus.ball
    assert fetched_routines[0].order_of_performance == 1
    assert fetched_routines[1].apparatus == Apparatus.clubs
    assert fetched_routines[1].order_of_performance == 2


def test_single_routine_per_apparatus_per_entry(db_session):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast)

    make_routine(db_session, entry, apparatus=Apparatus.rope)

    with pytest.raises(IntegrityError):
        make_routine(db_session, entry, apparatus=Apparatus.rope)
        db_session.commit()


# == Relationships and foreign keys ==#
def test_routine_entry_relationship(db_session):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast)

    make_routine(db_session, entry)

    db_session.commit()

    fetched_routine = db_session.query(Routine).first()
    assert fetched_routine.entry == entry
    assert fetched_routine.gymnast == gymnast


def test_routine_gymnast_property_for_gymnast_entry(db_session):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast=gymnast)

    routine = make_routine(db_session, entry)
    db_session.commit()

    assert routine.gymnast == gymnast
    assert routine.group is None


def test_routine_group_property_for_group_entry(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    group = make_group(db_session, club)
    meet = make_meet(db_session)
    entry = make_meet_entry(db_session, meet, group=group)

    routine = make_routine(db_session, entry)
    db_session.commit()

    assert routine.group == group
    assert routine.gymnast is None


# == Cascasde delete ==
def test_cascade_delete_entry(db_session):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast)
    make_routine(db_session, entry, apparatus=Apparatus.ball)
    make_routine(db_session, entry, apparatus=Apparatus.hoop)

    db_session.commit()

    db_session.delete(entry)
    db_session.commit()

    routines = db_session.query(Routine).filter_by(entry_id=entry.id).all()
    assert len(routines) == 0
    assert db_session.query(MeetEntry).count() == 0


# == RoutineProfile resolution (music_url join) ==#
def test_routine_music_url_resolves_from_gymnast_profile(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    gymnast = make_gymnast(db_session, club=club)
    make_routine_profile(
        db_session,
        gymnast=gymnast,
        apparatus=Apparatus.hoop,
        level=Level.level_3,
        music_url="gymnast-track.mp3",
    )
    meet = make_meet(db_session)
    entry = make_meet_entry(db_session, meet, gymnast=gymnast, level=Level.level_3)
    routine = make_routine(db_session, entry, apparatus=Apparatus.hoop)
    db_session.commit()

    assert routine.music_url == "gymnast-track.mp3"


def test_routine_music_url_resolves_from_group_profile(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    group = make_group(db_session, club, name="Team Group")
    make_routine_profile(
        db_session,
        group=group,
        apparatus=Apparatus.ball,
        level=Level.level_3,
        music_url="group-track.mp3",
    )
    meet = make_meet(db_session)
    entry = make_meet_entry(db_session, meet, group=group, level=Level.level_3)
    routine = make_routine(db_session, entry, apparatus=Apparatus.ball)
    db_session.commit()

    assert routine.music_url == "group-track.mp3"


def test_routine_music_url_none_when_no_matching_profile(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    gymnast = make_gymnast(db_session, club=club)
    # Profile exists for level_3, but the entry below is registered at level_4.
    make_routine_profile(
        db_session,
        gymnast=gymnast,
        apparatus=Apparatus.hoop,
        level=Level.level_3,
        music_url="gymnast-track.mp3",
    )
    meet = make_meet(db_session)
    entry = make_meet_entry(db_session, meet, gymnast=gymnast, level=Level.level_4)
    routine = make_routine(db_session, entry, apparatus=Apparatus.hoop)
    db_session.commit()

    assert routine.music_url is None
