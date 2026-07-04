"""
Tests for the RoutineProfile model.

Covers:
- Creation with required fields, owned by a gymnast
- Creation with required fields, owned by a group
- Exactly one of gymnast_id/group_id must be set (CheckConstraint)
- apparatus is required
- level is required
- music_url and choreography_notes are optional
- UniqueConstraint on (gymnast_id, group_id, apparatus, level)
- Same apparatus/level allowed for different gymnasts
- Deleting a gymnast cascades to their RoutineProfile rows
- Deleting a group cascades to their RoutineProfile rows
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Apparatus, Level, RoutineProfile
from test.conftest import make_club, make_district, make_group, make_gymnast, make_routine_profile


##-- Creation Tests --##
def test_create_routine_profile_owned_by_gymnast(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district)
    gymnast = make_gymnast(db_session, club=club)
    make_routine_profile(
        db_session, gymnast=gymnast, apparatus=Apparatus.hoop, level=Level.level_3, music_url="hoop.mp3"
    )
    db_session.commit()

    fetched = db_session.query(RoutineProfile).filter_by(gymnast_id=gymnast.id).first()
    assert fetched is not None
    assert fetched.group_id is None
    assert fetched.apparatus == Apparatus.hoop
    assert fetched.level == Level.level_3
    assert fetched.music_url == "hoop.mp3"


def test_create_routine_profile_owned_by_group(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district)
    group = make_group(db_session, club=club, name="Team A")
    make_routine_profile(
        db_session, group=group, apparatus=Apparatus.ball, level=Level.level_4, music_url="ball.mp3"
    )
    db_session.commit()

    fetched = db_session.query(RoutineProfile).filter_by(group_id=group.id).first()
    assert fetched is not None
    assert fetched.gymnast_id is None
    assert fetched.apparatus == Apparatus.ball
    assert fetched.level == Level.level_4
    assert fetched.music_url == "ball.mp3"


def test_routine_profile_without_music_url_succeeds(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district)
    gymnast = make_gymnast(db_session, club=club)
    profile = RoutineProfile(
        gymnast_id=gymnast.id, apparatus=Apparatus.clubs, level=Level.level_3, music_url=None
    )
    db_session.add(profile)
    db_session.commit()

    fetched = db_session.query(RoutineProfile).filter_by(gymnast_id=gymnast.id).first()
    assert fetched.music_url is None


##-- CheckConstraint (exactly one of gymnast_id/group_id) --##
def test_routine_profile_without_gymnast_or_group_fails(db_session):
    profile = RoutineProfile(apparatus=Apparatus.hoop, level=Level.level_3, music_url="hoop.mp3")
    db_session.add(profile)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_routine_profile_with_both_gymnast_and_group_fails(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district)
    gymnast = make_gymnast(db_session, club=club)
    group = make_group(db_session, club=club, name="Team A")

    profile = RoutineProfile(
        gymnast_id=gymnast.id,
        group_id=group.id,
        apparatus=Apparatus.hoop,
        level=Level.level_3,
        music_url="hoop.mp3",
    )
    db_session.add(profile)
    with pytest.raises(IntegrityError):
        db_session.commit()


##-- Required field tests --##
def test_routine_profile_without_apparatus_fails(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district)
    gymnast = make_gymnast(db_session, club=club)

    profile = RoutineProfile(gymnast_id=gymnast.id, apparatus=None, level=Level.level_3)
    db_session.add(profile)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_routine_profile_without_level_fails(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district)
    gymnast = make_gymnast(db_session, club=club)

    profile = RoutineProfile(gymnast_id=gymnast.id, apparatus=Apparatus.hoop, level=None)
    db_session.add(profile)
    with pytest.raises(IntegrityError):
        db_session.commit()


##-- UniqueConstraint tests --##
def test_duplicate_gymnast_apparatus_level_fails(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district)
    gymnast = make_gymnast(db_session, club=club)
    make_routine_profile(db_session, gymnast=gymnast, apparatus=Apparatus.hoop, level=Level.level_3)
    db_session.commit()

    duplicate = RoutineProfile(gymnast_id=gymnast.id, apparatus=Apparatus.hoop, level=Level.level_3)
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_duplicate_group_apparatus_level_fails(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district)
    group = make_group(db_session, club=club, name="Team A")
    make_routine_profile(db_session, group=group, apparatus=Apparatus.ball, level=Level.level_4)
    db_session.commit()

    duplicate = RoutineProfile(group_id=group.id, apparatus=Apparatus.ball, level=Level.level_4)
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_same_apparatus_and_level_allowed_for_different_gymnasts(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district)
    gymnast1 = make_gymnast(db_session, club=club, first_name="Alice", last_name="Smith")
    gymnast2 = make_gymnast(db_session, club=club, first_name="Bob", last_name="Jones")

    make_routine_profile(db_session, gymnast=gymnast1, apparatus=Apparatus.hoop, level=Level.level_3)
    make_routine_profile(db_session, gymnast=gymnast2, apparatus=Apparatus.hoop, level=Level.level_3)
    db_session.commit()

    fetched = db_session.query(RoutineProfile).filter_by(apparatus=Apparatus.hoop, level=Level.level_3).all()
    assert len(fetched) == 2


def test_same_gymnast_different_level_allowed(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district)
    gymnast = make_gymnast(db_session, club=club)

    make_routine_profile(db_session, gymnast=gymnast, apparatus=Apparatus.hoop, level=Level.level_3)
    make_routine_profile(db_session, gymnast=gymnast, apparatus=Apparatus.hoop, level=Level.level_4)
    db_session.commit()

    fetched = db_session.query(RoutineProfile).filter_by(gymnast_id=gymnast.id).all()
    assert len(fetched) == 2


##-- Cascade delete tests --##
def test_deleting_gymnast_cascades_to_routine_profile(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district)
    gymnast = make_gymnast(db_session, club=club)
    make_routine_profile(db_session, gymnast=gymnast, apparatus=Apparatus.hoop, level=Level.level_3)
    db_session.commit()

    db_session.delete(gymnast)
    db_session.commit()

    assert db_session.query(RoutineProfile).filter_by(gymnast_id=gymnast.id).count() == 0


def test_deleting_group_cascades_to_routine_profile(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district)
    group = make_group(db_session, club=club, name="Team A")
    make_routine_profile(db_session, group=group, apparatus=Apparatus.ball, level=Level.level_4)
    db_session.commit()

    db_session.delete(group)
    db_session.commit()

    assert db_session.query(RoutineProfile).filter_by(group_id=group.id).count() == 0
