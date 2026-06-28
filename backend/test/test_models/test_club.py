"""
Tests for the Club model, including:
- Creation of clubs with valid data
- Validation of required fields (name, abbreviation, district_id)
- Validation of unique name and abbreviation across clubs
- Same name and abbreviation can exist in different districts
- Club relationships with District, Coach, and Gymnast models
- Restriction on deletion of clubs with associated gymnasts or coaches
- Creation of coaches with valid data and association to clubs
- Creation of gymnasts with valid data and association to clubs
- Deletion of clubs with no associated gymnasts or coaches
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Club
from test.conftest import make_club, make_coach, make_district, make_gymnast


def test_club_create_with_valid_data(db_session):
    district = make_district(db_session, name="Northern District", abbreviation="ND")
    club = Club(name="Northern Stars", abbreviation="NS", district_id=district.id)

    db_session.add(club)
    db_session.commit()

    assert db_session.query(Club).filter_by(name="Northern Stars").first() is not None
    assert db_session.query(Club).filter_by(abbreviation="NS").first() is not None
    assert db_session.query(Club).filter_by(district_id=district.id).first() is not None


def test_club_name_required(db_session):
    district = make_district(db_session, name="Southern District", abbreviation="SD")
    club = Club(name=None, abbreviation="SS", district_id=district.id)

    db_session.add(club)

    with pytest.raises(IntegrityError):
        db_session.commit()

    def test_club_abbreviation_required(db_session):
        district = make_district(db_session, name="Eastern District", abbreviation="ED")
        club = Club(name="Eastern Eagles", abbreviation=None, district_id=district.id)

        db_session.add(club)

        with pytest.raises(IntegrityError):
            db_session.commit()


def test_club_district_id_required(db_session):
    club = Club(name="Western Wolves", abbreviation="WW", district_id=None)

    db_session.add(club)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_club_name_unique_within_district(db_session):
    district = make_district(db_session, name="Central District", abbreviation="CD")
    club1 = Club(name="Central Champions", abbreviation="CC", district_id=district.id)
    club2 = Club(name="Central Champions", abbreviation="CC2", district_id=district.id)

    db_session.add(club1)
    db_session.add(club2)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_club_abbreviation_unique_within_district(db_session):
    district = make_district(db_session, name="Capital District", abbreviation="CAP")
    club1 = Club(name="Capital Kings", abbreviation="CK", district_id=district.id)
    club2 = Club(name="Capital Queens", abbreviation="CK", district_id=district.id)

    db_session.add(club1)
    db_session.add(club2)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_club_same_name_abbreviation_different_districts_allowed(db_session):
    district1 = make_district(db_session, name="District One", abbreviation="D1")
    district2 = make_district(db_session, name="District Two", abbreviation="D2")

    make_club(db_session, name="Shared Club", abbreviation="SC", district=district1)
    make_club(db_session, name="Shared Club", abbreviation="SC", district=district2)

    db_session.commit()

    assert db_session.query(Club).filter_by(name="Shared Club").count() == 2


## -- Relationship Tests -- ##
def test_club_relationship_with_district(db_session):
    district = make_district(db_session, name="Relationship District", abbreviation="RD")
    make_club(db_session, name="Relationship Club", abbreviation="RC", district=district)

    db_session.commit()

    fetched_club = db_session.query(Club).filter_by(name="Relationship Club").first()
    assert fetched_club.district == district
    assert fetched_club.district.clubs[0] == fetched_club


def test_club_relationship_with_coaches(db_session):
    district = make_district(db_session, name="Coach District", abbreviation="CD")
    club = make_club(db_session, name="Coach Club", abbreviation="CC", district=district)
    coach1 = make_coach(db_session, first_name="Alice", last_name="Smith", club=club)
    coach2 = make_coach(db_session, first_name="Bob", last_name="Johnson", club=club)

    db_session.commit()

    fetched_club = db_session.query(Club).filter_by(name="Coach Club").first()
    assert len(fetched_club.coaches) == 2
    assert coach1 in fetched_club.coaches
    assert coach2 in fetched_club.coaches


def test_club_relationship_with_gymnasts(db_session):
    district = make_district(db_session, name="Gymnast District", abbreviation="GD")
    club = make_club(db_session, name="Gymnast Club", abbreviation="GC", district=district)
    gymnast1 = make_gymnast(db_session, first_name="Charlie", last_name="Brown", club=club)
    gymnast2 = make_gymnast(db_session, first_name="Daisy", last_name="Miller", club=club)

    db_session.commit()

    fetched_club = db_session.query(Club).filter_by(name="Gymnast Club").first()
    assert len(fetched_club.gymnasts) == 2
    assert gymnast1 in fetched_club.gymnasts
    assert gymnast2 in fetched_club.gymnasts


# -- Deletion Tests --#
def test_club_deletion_with_associated_gymnasts_restricted(db_session):
    district = make_district(db_session, name="Delete District", abbreviation="DD")
    club = make_club(db_session, name="Delete Club", abbreviation="DC", district=district)
    make_gymnast(db_session, first_name="Eve", last_name="Adams", club=club)

    db_session.delete(club)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_club_deletion_with_associated_coaches_restricted(db_session):
    district = make_district(db_session, name="Delete Coach District", abbreviation="DCD")
    club = make_club(db_session, name="Delete Coach Club", abbreviation="DCC", district=district)
    make_coach(db_session, first_name="Frank", last_name="Green", club=club)

    db_session.delete(club)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_club_deletion_with_no_associations_allowed(db_session):
    district = make_district(db_session, name="Safe Delete District", abbreviation="SDD")
    club = make_club(db_session, name="Safe Delete Club", abbreviation="SDC", district=district)

    db_session.delete(club)
    db_session.commit()

    assert db_session.query(Club).filter_by(name="Safe Delete Club").first() is None
