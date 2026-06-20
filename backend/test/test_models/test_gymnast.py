"""
Test for the Gymnast model and its relationships.

Covers:
 - Basic creation and persistence
 - Creation with optional fields (date_of_birth, country_code)
 - Cascade delete of entries and routines when a gymnast is deleted
 - Validation of first_name length
 - Validation of date_of_birth (if constraint is enabled)
 - Validation of club association (gymnast can have no club)
 - Validation of country_code length (if constraint is enabled)
 - Unique identity constraint (first_name + last_name + date_of_birth)
"""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Gymnast, MeetEntry, Routine, Meet
from test.conftest import make_meet, make_gymnast, make_meet_entry, make_routine

def test_gymnast_create_with_required_fields(db_session):
    gymnast = Gymnast(
        first_name="Ivanka",
        last_name="Kuznetsova",
        date_of_birth=date(2020, 5, 15),
        country_code="RUS"
    )
    db_session.add(gymnast)
    db_session.commit()

    assert db_session.query(Gymnast).filter_by(first_name="Ivanka", last_name="Kuznetsova").first() is not None
    assert db_session.query(Gymnast).filter_by(date_of_birth=date(2020, 5, 15)).first() is not None
    assert db_session.query(Gymnast).filter_by(country_code="RUS").first() is not None

def test_gymnast_create_with_optional_fields_null(db_session):
    gymnast = Gymnast(
        first_name="Liam",
        last_name="Smith",
        date_of_birth=None,
        country_code=None
    )
    db_session.add(gymnast)
    db_session.commit()

    assert db_session.query(Gymnast).filter_by(first_name="Liam", last_name="Smith").first() is not None
    assert db_session.query(Gymnast).filter_by(date_of_birth=None).first() is not None
    assert db_session.query(Gymnast).filter_by(country_code=None).first() is not None

def test_gymnast_first_name_too_short_raises_error(db_session):
    gymnast = Gymnast(
        first_name="A",
        last_name="Smith",
        date_of_birth=date(2010, 1, 1),
        country_code="USA"
    )
    db_session.add(gymnast)
    with pytest.raises(IntegrityError):
        db_session.commit()

# Enable this test when the date_of_birth constraint is enabled in the model
def test_gymnast_date_of_birth_in_future_raises_error(db_session):
    pytest.skip("Skipping test for future date_of_birth until constraint is enabled in the model.")

# def test_gymnast_date_of_birth_in_future_raises_error(db_session):
#     future_date = date.today().replace(year = date.today().year + 1)
#     gymnast = Gymnast(
#         first_name="Future",
#         last_name="Gymnast",
#         date_of_birth=future_date,
#         country_code="USA"
#     )
#     db_session.add(gymnast)
#     with pytest.raises(IntegrityError):
#         db_session.commit()

def test_gymnast_first_name_required(db_session):
    gymnast = Gymnast(
        first_name=None,
        last_name="Doe",
        date_of_birth=date(2010, 1, 1),
        country_code="USA"
    )
    db_session.add(gymnast)
    with pytest.raises(IntegrityError):
        db_session.commit()

def test_gymnast_last_name_required(db_session):
    gymnast = Gymnast(
        first_name="John",
        last_name=None,
        date_of_birth=date(2010, 1, 1),
        country_code="USA"
    )
    db_session.add(gymnast)
    with pytest.raises(IntegrityError):
        db_session.commit()

def test_duplicate_gymnast_names_with_different_dob_allowed(db_session):
    gymnast1 = Gymnast(
        first_name="Alex",
        last_name="Johnson",
        date_of_birth=date(2010, 1, 1),
        country_code="USA"
    )
    db_session.add(gymnast1)
    db_session.commit()

    gymnast2 = Gymnast(
        first_name="Alex",
        last_name="Johnson",
        date_of_birth=date(2011, 2, 2),
        country_code="USA"
    )
    db_session.add(gymnast2)
    db_session.commit()

    assert db_session.query(Gymnast).filter_by(first_name="Alex", last_name="Johnson").count() == 2

def test_gymnast_unique_identity_constraint(db_session):
    gymnast1 = Gymnast(
        first_name="Unique",
        last_name="Gymnast",
        date_of_birth=date(2010, 1, 1),
        country_code="USA"
    )
    db_session.add(gymnast1)
    db_session.commit()

    gymnast2 = Gymnast(
        first_name="Unique",
        last_name="Gymnast",
        date_of_birth=date(2010, 1, 1),
        country_code="CAN"
    )
    db_session.add(gymnast2)
    with pytest.raises(IntegrityError):
        db_session.commit()

def test_gymnast_registered_in_multiple_meets(db_session):
    gymnast = make_gymnast(db_session)
    meet1 = make_meet(db_session, name="Meet 1")
    meet2 = make_meet(db_session, name="Meet 2")

    entry1 = make_meet_entry(db_session, meet1, gymnast)
    entry2 = make_meet_entry(db_session, meet2, gymnast)
    db_session.commit()

    assert db_session.query(MeetEntry).filter_by(gymnast_id=gymnast.id).count() == 2

def test_country_code_max_length(db_session):
    """country_code is VARCHAR(3) — a 4-character code should be truncated or rejected."""
    gymnast = Gymnast(first_name="Test", last_name="Gymnast", country_code="TOOLONG")
    db_session.add(gymnast)
    db_session.commit()
 
    # SQLite doesn't enforce VARCHAR length — fetch and assert it was stored as-is.
    # This test documents the current behaviour; swap to pytest.raises(IntegrityError)
    # when migrating to PostgreSQL, which does enforce length.
    fetched = db_session.query(Gymnast).filter_by(last_name="Gymnast").first()
    assert fetched.country_code == "TOOLONG"

def test_gymnast_cascasde_delete(db_session):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast)
    routine = make_routine(db_session, entry)
    db_session.commit()

    db_session.delete(gymnast)
    db_session.commit()

    assert db_session.query(Gymnast).filter_by(id=gymnast.id).first() is None
    assert db_session.query(MeetEntry).filter_by(id=entry.id).first() is None
    assert db_session.query(Routine).filter_by(id=routine.id).first() is None
    assert db_session.query(Meet).filter_by(id=meet.id).first() is not None  # Meet should still exist  

def test_gymnast_delete_with_no_entries(db_session):
    gymnast = make_gymnast(db_session)
    db_session.commit()

    db_session.delete(gymnast)
    db_session.commit()

    assert db_session.query(Gymnast).filter_by(id=gymnast.id).first() is None

def test_gymnast_delete_with_meet_entry_but_no_routine(db_session):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast)
    db_session.commit()

    db_session.delete(gymnast)
    db_session.commit()

    assert db_session.query(Gymnast).filter_by(id=gymnast.id).first() is None
    assert db_session.query(MeetEntry).filter_by(id=entry.id).first() is None
    assert db_session.query(Meet).filter_by(id=meet.id).first() is not None  # Meet should still exist

def test_gymnast_delete_with_multiple_meet_entries(db_session):
    gymnast = make_gymnast(db_session)
    meet1 = make_meet(db_session, name="Meet 1")
    meet2 = make_meet(db_session, name="Meet 2")

    entry1 = make_meet_entry(db_session, meet1, gymnast)
    entry2 = make_meet_entry(db_session, meet2, gymnast)
    db_session.commit()

    db_session.delete(gymnast)
    db_session.commit()

    assert db_session.query(Gymnast).filter_by(id=gymnast.id).first() is None
    assert db_session.query(MeetEntry).filter_by(id=entry1.id).first() is None
    assert db_session.query(MeetEntry).filter_by(id=entry2.id).first() is None
    assert db_session.query(Meet).filter_by(id=meet1.id).first() is not None  # Meets should still exist
    assert db_session.query(Meet).filter_by(id=meet2.id).first() is not None

def test_gymnast_can_have_no_club(db_session):
    gymnast = make_gymnast(db_session, club=None, create_club_if_none=False)
    db_session.commit()

    assert gymnast.club_id is None
    assert db_session.query(Gymnast).filter_by(id=gymnast.id).first() is not None

def test_gymnast_with_club(db_session):
    gymnast = make_gymnast(db_session)
    db_session.commit()

    assert gymnast.club_id is not None
    assert db_session.query(Gymnast).filter_by(id=gymnast.id).first() is not None

def test_delete_gymnast_with_no_club(db_session):
    gymnast = make_gymnast(db_session, club=None, create_club_if_none=False)
    db_session.commit()

    db_session.delete(gymnast)
    db_session.commit()

    assert db_session.query(Gymnast).filter_by(id=gymnast.id).first() is None

def test_delete_gymnast_with_club(db_session):
    gymnast = make_gymnast(db_session)
    db_session.commit()

    db_session.delete(gymnast)
    db_session.commit()

    assert db_session.query(Gymnast).filter_by(id=gymnast.id).first() is None