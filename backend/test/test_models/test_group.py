"""
Tests for the Group model.

Covers:
- Creation with required fields
- club_id is required
- name is required
- UniqueConstraint on (club_id, name)
- Same group name allowed across different clubs
- A group can be created with no members
- Gymnast.group_id links a gymnast to a group
- A gymnast without a group has group_id = None
- Multiple gymnasts can belong to the same group
- Group relationship to club and members
- Deleting a gymnast does not delete its group
- Deleting a group directly succeeds when it has no members
- Deleting a group with members is rejected (RESTRICT)
- Deleting a club with a group is rejected (RESTRICT)
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Group, Gymnast
from test.conftest import make_club, make_district, make_group, make_gymnast


##-- Creation Tests --##
def test_create_group_with_required_fields(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district)
    make_group(db_session, club=club, name="Senior Group A")
    db_session.commit()

    fetched = db_session.query(Group).filter_by(name="Senior Group A").first()
    assert fetched.name == "Senior Group A"
    assert fetched.club_id == club.id

def test_create_group_without_club_id_fails(db_session):
    group = Group(name="Junior Group B", club_id=None)
    db_session.add(group)
    with pytest.raises(IntegrityError):
        db_session.commit()

def test_create_group_without_name_fails(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district)
    group = Group(name=None, club_id=club.id)
    db_session.add(group)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_create_group_with_duplicate_name_in_same_club_fails(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district)
    make_group(db_session, club=club, name="Elite Group")
    db_session.commit()

    duplicate_group = Group(name="Elite Group", club_id=club.id)
    db_session.add(duplicate_group)
    with pytest.raises(IntegrityError):
        db_session.commit()

def test_create_group_with_no_members(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district)
    make_group(db_session, club=club, name="Group with No Members")
    db_session.commit()

    fetched = db_session.query(Group).filter_by(name="Group with No Members").first()
    assert fetched is not None
    assert len(fetched.members) == 0

##-- UniqueConstraint Tests --##
def test_same_group_name_allowed_across_different_clubs(db_session):
    district = make_district(db_session)
    club1 = make_club(db_session, district=district, name="Club One")
    club2 = make_club(db_session, district=district, name="Club Two")

    make_group(db_session, club=club1, name="Shared Group Name")
    make_group(db_session, club=club2, name="Shared Group Name")
    db_session.commit()

    group1 = db_session.query(Group).filter_by(club_id=club1.id).first()
    group2 = db_session.query(Group).filter_by(club_id=club2.id).first()

    assert group1.name == "Shared Group Name"
    assert group2.name == "Shared Group Name"

def test_group_relationship_to_club_and_members(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district, name="Club A")
    group = make_group(db_session, club=club, name="Group A")

    gymnast1 = make_gymnast(db_session, first_name="Alice", last_name="Smith", club=club, group=group)
    gymnast2 = make_gymnast(db_session, first_name="Bob", last_name="Johnson", club=club, group=group)

    db_session.commit()

    fetched_group = db_session.query(Group).filter_by(id=group.id).first()
    assert fetched_group.club.id == club.id
    assert len(fetched_group.members) == 2
    assert gymnast1 in fetched_group.members
    assert gymnast2 in fetched_group.members

def test_group_name_unique_within_club(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district, name="Club A")
    make_group(db_session, club=club, name="Unique Group")
    db_session.commit()

    duplicate_group = Group(name="Unique Group", club_id=club.id)
    db_session.add(duplicate_group)
    with pytest.raises(IntegrityError):
        db_session.commit()

##-- Gymnast group id memmbershiip
def test_gymnast_without_group_id_has_no_group(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district, name="Club A")
    gymnast = make_gymnast(db_session, first_name="Charlie", last_name="Brown", club=club, group=None)
    db_session.commit()

    fetched_gymnast = db_session.query(Gymnast).filter_by(id=gymnast.id).first()
    assert fetched_gymnast.group_id is None

def test_gymnast_can_be_assigned_to_group(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district, name="Club A")
    group = make_group(db_session, club=club, name="Group A")
    gymnast = make_gymnast(db_session, first_name="Daisy", last_name="Miller", club=club, group=group)
    db_session.commit()

    fetched_gymnast = db_session.query(Gymnast).filter_by(id=gymnast.id).first()
    assert fetched_gymnast.group_id == group.id

def test_multiple_gymnasts_can_belong_to_same_group(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district, name="Club A")
    group = make_group(db_session, club=club, name="Group A")

    gymnast1 = make_gymnast(db_session, first_name="Eve", last_name="Davis", club=club, group=group)
    gymnast2 = make_gymnast(db_session, first_name="Frank", last_name="Wilson", club=club, group=group)
    db_session.commit()

    fetched_group = db_session.query(Group).filter_by(id=group.id).first()
    assert len(fetched_group.members) == 2
    assert gymnast1 in fetched_group.members
    assert gymnast2 in fetched_group.members

##-- Relationship and Deletion Tests --##
def test_deleting_gymnast_does_not_delete_group(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district, name="Club A")
    group = make_group(db_session, club=club, name="Group A")
    gymnast = make_gymnast(db_session, first_name="Grace", last_name="Lee", club=club, group=group)
    db_session.commit()

    db_session.delete(gymnast)
    db_session.commit()

    fetched_group = db_session.query(Group).filter_by(id=group.id).first()
    assert fetched_group is not None

def test_group_club_relationship(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district, name="Club A")
    group = make_group(db_session, club=club, name="Group A")
    db_session.commit()

    fetched_group = db_session.query(Group).filter_by(id=group.id).first()
    assert fetched_group.club == club
    assert fetched_group.club.district == district

def test_group_memebers_relationship(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district, name="Club A")
    group = make_group(db_session, club=club, name="Group A")

    gymnast1 = make_gymnast(db_session, first_name="Hannah", last_name="Taylor", club=club, group=group)
    gymnast2 = make_gymnast(db_session, first_name="Ian", last_name="Anderson", club=club, group=group)
    db_session.commit()

    fetched_group = db_session.query(Group).filter_by(id=group.id).first()
    assert len(fetched_group.members) == 2
    assert gymnast1 in fetched_group.members
    assert gymnast2 in fetched_group.members

def test_gymnast_group_relationship(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district, name="Club A")
    group = make_group(db_session, club=club, name="Group A")
    gymnast = make_gymnast(db_session, first_name="Jack", last_name="Thomas", club=club, group=group)
    independent_gymnast = make_gymnast(db_session, first_name="Lily", last_name="White", club=club, group=None)
    db_session.commit()

    assert gymnast.group == group
    assert independent_gymnast.group is None

def test_deleting_group_with_members_rejected(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district, name="Club A")
    group = make_group(db_session, club=club, name="Group A")
    make_gymnast(db_session, first_name="Mia", last_name="Harris", club=club, group=group)
    db_session.commit()

    db_session.delete(group)
    with pytest.raises(IntegrityError):
        db_session.commit()

def test_deleting_a_group_without_members_succeeds(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district, name="Club A")
    group = make_group(db_session, club=club, name="Group A")
    db_session.commit()

    db_session.delete(group)
    db_session.commit()

    fetched_group = db_session.query(Group).filter_by(id=group.id).first()
    assert fetched_group is None

def test_deleting_club_with_group_rejected(db_session):
    district = make_district(db_session)
    club = make_club(db_session, district=district, name="Club A")
    make_group(db_session, club=club, name="Group A")
    db_session.commit()

    db_session.delete(club)
    with pytest.raises(IntegrityError):
        db_session.commit()
