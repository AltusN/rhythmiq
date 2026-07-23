"""
Tests for the MeetEntry model, including:
- Creation with required fields, and its meet/gymnast relationships
- bib_number required, level required
- entry_fee defaults to False and can be set to True
- Unique constraint on (meet, gymnast) -- same gymnast can enter different meets, and
  different gymnasts can enter the same meet
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import AgeGroup, Level, MeetEntry
from test.conftest import make_gymnast, make_meet, make_meet_entry


def test_meet_entry_create_with_required_fields(db_session):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    make_meet_entry(db_session, meet, gymnast)

    db_session.commit()

    fetched = db_session.query(MeetEntry).first()
    assert fetched is not None
    assert fetched.meet_id == meet.id
    assert fetched.gymnast_id == gymnast.id
    assert fetched.age_group == AgeGroup.under_12
    assert fetched.level == Level.level_3
    assert fetched.bib_number == "A123"


def test_meet_entry_meet_relationship(db_session):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    make_meet_entry(db_session, meet, gymnast)

    db_session.commit()

    fetched_entry = db_session.query(MeetEntry).first()
    assert fetched_entry.meet == meet


def test_meet_entry_gymnast_relationship(db_session):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    make_meet_entry(db_session, meet, gymnast)

    db_session.commit()

    fetched_entry = db_session.query(MeetEntry).first()
    assert fetched_entry.gymnast == gymnast


def test_meet_entry_bib_number_not_null(db_session):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)

    # Create a meet entry with a null bib
    entry = MeetEntry(
        meet_id=meet.id,
        gymnast_id=gymnast.id,
        age_group=AgeGroup.under_8,
        level=Level.level_1,
        bib_number=None,
    )

    db_session.add(entry)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_meet_entry_entry_fee_defaults_to_false(db_session):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    make_meet_entry(db_session, meet, gymnast)

    db_session.commit()

    fetched_entry = db_session.query(MeetEntry).first()
    assert fetched_entry.entry_fee_paid is False


def test_meet_entry_entry_fee_can_be_set_to_true(db_session):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast)
    entry.entry_fee_paid = True

    db_session.commit()

    fetched_entry = db_session.query(MeetEntry).first()
    assert fetched_entry.entry_fee_paid is True


def test_meet_entry_level_required(db_session):
    # Missing level should raise and integrity error
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)

    # Create a meet with a missing level
    entry = MeetEntry(
        meet_id=meet.id,
        gymnast_id=gymnast.id,
        age_group=AgeGroup.under_8,
        level=None,  # Missing level
        bib_number="A125",
    )
    db_session.add(entry)

    with pytest.raises(IntegrityError):
        db_session.commit()


## -- Unique constraints and validations -- ##
def test_meet_entry_unique_constraint(db_session):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    make_meet_entry(db_session, meet, gymnast, bib_number="A123")

    db_session.commit()

    # Attempt to create a second entry with the same meet and gymnast
    entry2 = MeetEntry(
        meet_id=meet.id,
        gymnast_id=gymnast.id,
        age_group=AgeGroup.under_12,
        level=Level.level_3,
        bib_number="A124",
    )
    db_session.add(entry2)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_same_gymnast_can_enter_different_meets(db_session):
    meet1 = make_meet(db_session, name="Meet 1")
    meet2 = make_meet(db_session, name="Meet 2")
    gymnast = make_gymnast(db_session)

    make_meet_entry(db_session, meet1, gymnast, bib_number="A123")
    make_meet_entry(db_session, meet2, gymnast, bib_number="B456")

    db_session.commit()

    fetched_entries = db_session.query(MeetEntry).filter_by(gymnast_id=gymnast.id).all()
    assert len(fetched_entries) == 2


def test_different_gymnast_can_enter_the_same_meet(db_session):
    meet = make_meet(db_session)
    gymnast1 = make_gymnast(db_session, first_name="Anna", last_name="Petrov")
    gymnast2 = make_gymnast(db_session, first_name="Maria", last_name="Ivanova")

    make_meet_entry(db_session, meet, gymnast1, bib_number="A123")
    make_meet_entry(db_session, meet, gymnast2, bib_number="A124")

    db_session.commit()

    fetched_entries = db_session.query(MeetEntry).filter_by(meet_id=meet.id).all()
    assert len(fetched_entries) == 2


def test_level_no_longer_has_retired_elite_members():
    # elite_1/elite_2/junior_elite were retired in favor of the full level_1-10 /
    # high_performance_1-4 / pre_junior / junior / senior / olympic taxonomy -- guard
    # against an accidental future re-add.
    assert "elite_1" not in Level.__members__
    assert "elite_2" not in Level.__members__
    assert "junior_elite" not in Level.__members__
    assert len(Level.__members__) == 18


NEW_AGE_GROUPS = [
    AgeGroup.under_7,
    AgeGroup.under_9,
    AgeGroup.under_11,
    AgeGroup.over_11,
    AgeGroup.under_13,
    AgeGroup.under_15,
    AgeGroup.over_15,
]


@pytest.mark.parametrize("age_group", NEW_AGE_GROUPS)
def test_meet_entry_accepts_the_new_age_groups(db_session, age_group):
    meet = make_meet(db_session)
    gymnast = make_gymnast(db_session)
    entry = make_meet_entry(db_session, meet, gymnast, age_group=age_group)
    db_session.commit()

    assert db_session.query(MeetEntry).filter_by(id=entry.id).one().age_group is age_group


def test_age_group_enum_order_matches_the_database(db_session):
    """
    Postgres sorts an enum by DEFINITION order, not alphabetically, so the order
    the migration built with BEFORE/AFTER must match AgeGroup's declaration order.
    Appending instead of positioning would put u7/u9/u11/o11 after o14 and make any
    ORDER BY on this column meaningless -- nothing else in the suite would notice.
    """
    stored = [
        row[0]
        for row in db_session.execute(
            text(
                "SELECT enumlabel FROM pg_enum e "
                "JOIN pg_type t ON t.oid = e.enumtypid "
                "WHERE t.typname = 'agegroup' ORDER BY enumsortorder"
            )
        )
    ]

    assert stored == [member.name for member in AgeGroup]
    assert stored == [
        "under_7",
        "under_8",
        "under_9",
        "under_10",
        "under_11",
        "over_11",
        "under_12",
        "under_13",
        "under_14",
        "under_15",
        "over_14",
        "over_15",
    ]
