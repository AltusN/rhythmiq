import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Club, District
from test.conftest import make_club, make_district

"""
Tests for the District model, including:
- Creation of districts with valid data
- Validation of required fields (name, abbreviation)
- Validation of unique abbreviation
- Validation of unique name across districts
- Restriction on deletion of districts with associated clubs
- Creation of clubs with valid data and association to districts
"""


def test_district_create_with_valid_data(db_session):
    district = District(name="Western Province", abbreviation="WP")

    db_session.add(district)
    db_session.commit()

    assert db_session.query(District).filter_by(name="Western Province").first() is not None
    assert db_session.query(District).filter_by(abbreviation="WP").first() is not None


def test_district_name_required(db_session):
    district = District(name=None, abbreviation="WP")

    db_session.add(district)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_district_abbreviation_required(db_session):
    district = District(name="Western Province", abbreviation=None)

    db_session.add(district)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_district_abbreviation_unique(db_session):
    district1 = District(name="Western Province", abbreviation="WP")
    district2 = District(name="Eastern Province", abbreviation="WP")

    db_session.add(district1)
    db_session.add(district2)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_district_name_is_unque_across_districts(db_session):
    district1 = District(name="Central Province", abbreviation="CP")
    district2 = District(name="Central Province", abbreviation="CP2")

    db_session.add(district1)
    db_session.add(district2)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_district_deletion_with_associated_clubs_restricted(db_session):
    district = make_district(db_session)
    make_club(db_session, district=district)

    db_session.delete(district)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_club_create_with_valid_data(db_session):
    district = make_district(db_session)
    club = Club(name="Elite Gymnastics", abbreviation="EG", district_id=district.id)

    db_session.add(club)
    db_session.commit()

    assert db_session.query(Club).filter_by(name="Elite Gymnastics").first() is not None
    assert db_session.query(Club).filter_by(abbreviation="EG").first() is not None
    assert db_session.query(Club).filter_by(district_id=district.id).first() is not None


def test_district_can_have_many_clubs(db_session):
    district = make_district(db_session)
    make_club(db_session, district=district, name="Club One", abbreviation="C1")
    make_club(db_session, district=district, name="Club Two", abbreviation="C2")

    db_session.commit()

    assert db_session.query(Club).filter_by(name="Club One").first() is not None
    assert db_session.query(Club).filter_by(name="Club Two").first() is not None
    assert db_session.query(Club).filter_by(district_id=district.id).count() == 2


def test_district_deletion_without_associated_clubs_allowed(db_session):
    district = make_district(db_session)

    db_session.delete(district)
    db_session.commit()

    assert db_session.query(District).filter_by(id=district.id).count() == 0
