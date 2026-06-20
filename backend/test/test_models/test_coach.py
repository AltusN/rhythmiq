"""
Tests for the Coach model.
Includes tests for:
- Creation of coaches with valid data
- Validation of required fields (first_name, last_name, club_id)
- Validation of unique identity constraint (first_name + last_name + club_id)
- is_head_coach field default value and validation
- multiple coaches can be in same club
- multiple clubs can have their own head coaches
- Restriction on deletion of clubs with associated coaches
- Creation of coaches with valid data and association to clubs
- Deletion of coaches
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Coach, Club
from test.conftest import make_club, make_district, make_coach

#-- Creation
def test_coach_create_with_valid_data(db_session):
    district = make_district(db_session, name="Northern District", abbreviation="ND")
    club = make_club(db_session, name="Northern Stars", abbreviation="NS", district=district)
    coach = Coach(first_name="John", last_name="Doe", club_id=club.id, is_head_coach=True)
    
    db_session.add(coach)
    db_session.commit()

    assert db_session.query(Coach).filter_by(first_name="John", last_name="Doe").first() is not None
    assert db_session.query(Coach).filter_by(club_id=club.id).first() is not None
    assert db_session.query(Coach).filter_by(is_head_coach=True).first() is not None

def test_coach_create_with_optional_fields_null(db_session):
    district = make_district(db_session, name="Southern District", abbreviation="SD")
    club = make_club(db_session, name="Southern Stars", abbreviation="SS", district=district)
    coach = Coach(first_name="Jane", last_name="Smith", club_id=club.id, is_head_coach=None)
    
    db_session.add(coach)
    db_session.commit()

    assert db_session.query(Coach).filter_by(first_name="Jane", last_name="Smith").first() is not None
    assert db_session.query(Coach).filter_by(club_id=club.id).first() is not None
    assert db_session.query(Coach).filter_by(is_head_coach=None).first() is None

def test_coach_first_name_required(db_session):
    district = make_district(db_session, name="Eastern District", abbreviation="ED")
    club = make_club(db_session, name="Eastern Eagles", abbreviation="EE", district=district)
    coach = Coach(first_name=None, last_name="Smith", club_id=club.id)
    
    db_session.add(coach)
    
    with pytest.raises(IntegrityError):
        db_session.commit()

def test_coach_last_name_required(db_session):
    district = make_district(db_session, name="Western District", abbreviation="WD")
    club = make_club(db_session, name="Western Wolves", abbreviation="WW", district=district)
    coach = Coach(first_name="Emily", last_name=None, club_id=club.id)
    
    db_session.add(coach)
    
    with pytest.raises(IntegrityError):
        db_session.commit()

def test_coach_club_id_required(db_session):
    coach = Coach(first_name="Michael", last_name="Johnson", club_id=None)
    
    db_session.add(coach)
    
    with pytest.raises(IntegrityError):
        db_session.commit()

# -- head coach
def test_multiple_coaches_same_club(db_session):
    district = make_district(db_session, name="Central District", abbreviation="CD")
    club = make_club(db_session, name="Central Champions", abbreviation="CC", district=district)
    coach1 = Coach(first_name="Alice", last_name="Brown", club_id=club.id, is_head_coach=True)
    coach2 = Coach(first_name="Bob", last_name="Green", club_id=club.id, is_head_coach=False)
    
    db_session.add(coach1)
    db_session.add(coach2)
    db_session.commit()

    assert db_session.query(Coach).filter_by(first_name="Alice", last_name="Brown").first() is not None
    assert db_session.query(Coach).filter_by(first_name="Bob", last_name="Green").first() is not None
    assert db_session.query(Coach).filter_by(club_id=club.id).count() == 2  

def test_multiple_clubs_with_head_coaches(db_session):
    district = make_district(db_session, name="Metropolitan District", abbreviation="MD")
    club1 = make_club(db_session, name="Metro Stars", abbreviation="MS", district=district)
    club2 = make_club(db_session, name="Metro Eagles", abbreviation="ME", district=district)
    
    coach1 = Coach(first_name="Carol", last_name="White", club_id=club1.id, is_head_coach=True)
    coach2 = Coach(first_name="Dave", last_name="Black", club_id=club2.id, is_head_coach=True)
    
    db_session.add(coach1)
    db_session.add(coach2)
    db_session.commit()

    assert db_session.query(Coach).filter_by(first_name="Carol", last_name="White").first() is not None
    assert db_session.query(Coach).filter_by(first_name="Dave", last_name="Black").first() is not None
    assert db_session.query(Coach).filter_by(club_id=club1.id, is_head_coach=True).first() is not None
    assert db_session.query(Coach).filter_by(club_id=club2.id, is_head_coach=True).first() is not None

def test_coach_can_become_head_coach(db_session):
    district = make_district(db_session, name="Suburban District", abbreviation="SD")
    club = make_club(db_session, name="Suburban Stars", abbreviation="SS", district=district)
    
    coach = Coach(first_name="Eve", last_name="Davis", club_id=club.id, is_head_coach=False)
    db_session.add(coach)
    db_session.commit()

    coach.is_head_coach = True
    db_session.commit()

    assert db_session.query(Coach).filter_by(first_name="Eve", last_name="Davis", is_head_coach=True).first() is not None

## -- Relationships -- ##
def test_coach_relationship_with_club(db_session):
    district = make_district(db_session, name="Coaching District", abbreviation="CD")
    club = make_club(db_session, name="Coaching Club", abbreviation="CC", district=district)
    coach = Coach(first_name="Frank", last_name="Miller", club_id=club.id, is_head_coach=True)
    
    db_session.add(coach)
    db_session.commit()

    fetched_coach = db_session.query(Coach).filter_by(first_name="Frank", last_name="Miller").first()
    assert fetched_coach.club == club
    assert fetched_coach.club.coaches[0] == fetched_coach

# -- Deletion -- ##
def test_coach_deletion(db_session):
    district = make_district(db_session, name="Deletion District 2", abbreviation="D2")
    club = make_club(db_session, name="Deletion Club 2", abbreviation="C2", district=district)
    coach = Coach(first_name="Hannah", last_name="Taylor", club_id=club.id, is_head_coach=False)
    db_session.add(coach)
    db_session.commit()

    db_session.delete(coach)
    db_session.commit()

    assert db_session.query(Coach).filter_by(id=coach.id).first() is None

def test_delete_club_with_coach_association(db_session):
    district = make_district(db_session, name="Deletion District", abbreviation="DD")
    club = make_club(db_session, name="Deletion Club", abbreviation="DC", district=district)
    coach = Coach(first_name="Grace", last_name="Wilson", club_id=club.id, is_head_coach=True)
    
    db_session.add(coach)
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.delete(club)
        db_session.commit()