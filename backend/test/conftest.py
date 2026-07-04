from datetime import date
from itertools import count

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.models import (
    AgeGroup,
    Apparatus,
    Base,
    Club,
    Coach,
    District,
    Group,
    Gymnast,
    Level,
    Meet,
    MeetEntry,
    MeetStatus,
    Routine,
    RoutineProfile,
)

_district_seq = count(1)
_club_seq = count(1)


@pytest.fixture(scope="function")
def db_session():
    """
    Provides a fresh in memory SQLite session for each test function

    - PRAGMA foreign_keys=ON is set to enforce foreign key constraints in SQLite. Default
    is off, and we need to test referential integrity.
    - Base.metadata.drop_all is not needed for in-memory SQLite databases as they are
    discarded after each test function. But may want to use postgress later
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    # Enable foreign key constraints in SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(db_conn, _):
        db_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


# == Helper functions to create database objects for testing ==#


def make_meet(
    db_session,
    district=None,
    name="Test Meet",
    location="Test Location",
    start_date=date(2026, 6, 1),
    end_date=date(2026, 6, 2),
    status=MeetStatus.scheduled,
) -> Meet:
    meet = Meet(
        district_id=district.id if district else None,
        name=name,
        location=location,
        start_date=start_date,
        end_date=end_date,
        status=status,
    )
    db_session.add(meet)
    db_session.flush()  # Get meet.id populated
    return meet


def make_district(db_session, name=None, abbreviation=None):
    idx = next(_district_seq)
    if name is None:
        name = f"Test District {idx}"
    if abbreviation is None:
        abbreviation = f"TD{idx}"
    district = District(name=name, abbreviation=abbreviation)
    db_session.add(district)
    db_session.flush()  # Get district.id populated
    return district


def make_club(db_session, district=None, name=None, abbreviation=None):
    idx = next(_club_seq)
    if name is None:
        name = f"Test Club {idx}"
    if abbreviation is None:
        abbreviation = f"TC{idx}"
    if district is None:
        district = make_district(db_session)
    club = Club(name=name, abbreviation=abbreviation, district_id=district.id)
    db_session.add(club)
    db_session.flush()  # Get club.id populated
    return club


def make_coach(db_session, first_name="John", last_name="Doe", club=None):
    if club is None:
        district = make_district(db_session)
        club = make_club(db_session, district=district)
    coach = Coach(first_name=first_name, last_name=last_name, club_id=club.id)
    db_session.add(coach)
    db_session.flush()  # Get coach.id populated
    return coach


def make_gymnast(
    db_session,
    first_name="Anna",
    last_name="Petrov",
    club=None, # Optional[Club] = None,
    group=None, # Optional[Group] = None,
    date_of_birth=date(2016, 10, 1),
    country_code="BLR",
    create_club_if_none=True,
) -> Gymnast:
    if club is None and create_club_if_none:
        district = make_district(db_session)
        club = make_club(db_session, district=district)

    gymnast = Gymnast(
        first_name=first_name,
        last_name=last_name,
        club_id=club.id if club else None,
        group_id=group.id if group else None,
        date_of_birth=date_of_birth,
        country_code=country_code,
    )
    db_session.add(gymnast)
    db_session.flush()  # Get gymnast.id populated
    return gymnast

def make_group(
    db_session,
    club,
    name="Test Group",
):
    group = Group(
        name=name,
        club_id=club.id,
    )
    db_session.add(group)
    db_session.flush()  # Get group.id populated
    return group


def make_meet_entry(
    db_session,
    meet,
    gymnast=None,
    group=None,
    age_group=AgeGroup.under_12,
    level=Level.level_3,
    bib_number="A123",
) -> MeetEntry:
    entry = MeetEntry(
        meet_id=meet.id,
        gymnast_id=gymnast.id if gymnast else None,
        group_id=group.id if group else None,
        age_group=age_group,
        level=level,
        bib_number=bib_number,
    )
    db_session.add(entry)
    db_session.flush()  # Get entry.id populated
    return entry

def make_routine_profile(
    db_session,
    gymnast=None,
    group=None,
    apparatus=Apparatus.freehand,
    level=Level.level_3,
    music_url="file:///c:/test_music.mp3",
) -> RoutineProfile:
    if gymnast is None and group is None:
        gymnast = make_gymnast(db_session)  # Create a default gymnast if none provided
    routine_profile = RoutineProfile(
        gymnast_id=gymnast.id if gymnast else None,
        group_id=group.id if group else None,
        apparatus=apparatus,
        level = level,
        music_url=music_url,
    )
    db_session.add(routine_profile)
    db_session.flush()  # Get routine_profile.id populated
    return routine_profile

def make_routine(
    db_session,
    meet_entry,
    apparatus=Apparatus.freehand,
    order_of_performance=1,
) -> Routine:
    routine = Routine(
        entry_id=meet_entry.id,
        apparatus=apparatus,
        order_of_performance=order_of_performance,
    )
    db_session.add(routine)
    db_session.flush()  # Get routine.id populated
    return routine
