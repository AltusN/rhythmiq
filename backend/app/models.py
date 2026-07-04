from datetime import date as date_type
from enum import StrEnum
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# Enums
class MeetStatus(StrEnum):
    draft = "draft"
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class Apparatus(StrEnum):
    rope = "rope"
    hoop = "hoop"
    ball = "ball"
    clubs = "clubs"
    ribbon = "ribbon"
    freehand = "freehand"


class AgeGroup(StrEnum):
    under_8 = "u8"
    under_10 = "u10"
    under_12 = "u12"
    under_14 = "u14"
    over_14 = "o14"


class Level(StrEnum):
    level_1 = "level_1"
    level_2 = "level_2"
    level_3 = "level_3"
    level_4 = "level_4"
    level_5 = "level_5"
    elite_1 = "elite_1"
    elite_2 = "elite_2"
    junior_elite = "junior_elite"
    junior = "junior"
    senior = "senior"


# Models
class Meet(Base):
    __tablename__ = "meets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    district_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("districts.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    location: Mapped[str] = mapped_column(String, index=True, nullable=False)
    start_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    end_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    status: Mapped[MeetStatus] = mapped_column(
        Enum(MeetStatus), default=MeetStatus.draft, nullable=False
    )

    district: Mapped[Optional["District"]] = relationship("District", back_populates="meets")

    entries: Mapped[list["MeetEntry"]] = relationship(
        "MeetEntry", back_populates="meet", cascade="all, delete-orphan"
    )

    __table_args__ = (CheckConstraint("end_date >= start_date", name="ck_meet_dates_valid"),)


class District(Base):
    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    abbreviation: Mapped[str] = mapped_column(String(10), index=True, nullable=False)

    # Restrict deletion of districts that have clubs associated with them
    clubs: Mapped[list["Club"]] = relationship(
        "Club", back_populates="district", passive_deletes=True
    )
    meets: Mapped[list["Meet"]] = relationship(
        "Meet", back_populates="district", passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint("abbreviation", name="uq_district_abbreviation"),
        UniqueConstraint("name", name="uq_district_name"),
    )


class Club(Base):
    __tablename__ = "clubs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    district_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("districts.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    abbreviation: Mapped[str] = mapped_column(String(10), index=True, nullable=False)

    district: Mapped["District"] = relationship("District", back_populates="clubs")

    # Restrict deletion of clubs that have gymnasts associated with them
    gymnasts: Mapped[list["Gymnast"]] = relationship(
        "Gymnast", back_populates="club", passive_deletes=True
    )
    coaches: Mapped[list["Coach"]] = relationship(
        "Coach", back_populates="club", passive_deletes=True
    )
    groups: Mapped[list["Group"]] = relationship(
        "Group", back_populates="club", passive_deletes="all"
    )

    __table_args__ = (
        UniqueConstraint("district_id", "name", name="uq_club_name"),
        UniqueConstraint("district_id", "abbreviation", name="uq_club_abbreviation"),
    )


class Coach(Base):
    __tablename__ = "coaches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    club_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clubs.id", ondelete="RESTRICT"), nullable=False
    )
    first_name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    last_name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    is_head_coach: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    club: Mapped["Club"] = relationship("Club", back_populates="coaches")

    __table_args__ = (
        UniqueConstraint("club_id", "first_name", "last_name", name="uq_coach_identity"),
    )


class Gymnast(Base):
    __tablename__ = "gymnasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Gymnast can be independent of a club, so club_id is optional
    club_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("clubs.id", ondelete="RESTRICT"), nullable=True
    )
    group_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("groups.id", ondelete="RESTRICT"), nullable=True
    )
    first_name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    last_name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    date_of_birth: Mapped[date_type | None] = mapped_column(Date)
    country_code: Mapped[str | None] = mapped_column(String(3), index=True)

    club: Mapped[Optional["Club"]] = relationship("Club", back_populates="gymnasts")
    entries: Mapped[list["MeetEntry"]] = relationship(
        "MeetEntry", back_populates="gymnast", cascade="all, delete-orphan"
    )
    group: Mapped["Group | None"] = relationship("Group", back_populates="members")

    __table_args__ = (
        CheckConstraint("length(first_name) > 2", name="ck_gymnast_first_name_nonempty"),
        # enable for production, but disable for testing to allow creation of test gymnasts with future DOB
        # CheckConstraint("date_of_birth <= current_date", name="ck_gymnast_date_of_birth_valid")
        UniqueConstraint("first_name", "last_name", "date_of_birth", name="uq_gymnast_identity"),
    )

class Group(Base):
    """
    Represents a group of gymnasts within a meet, typically based on age group and level.
    """
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    club_id: Mapped[int] = mapped_column(Integer, ForeignKey("clubs.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String, index=True, nullable=False)

    club: Mapped["Club"] = relationship("Club", back_populates="groups")
    # Restrict deletion of groups that have gymnasts associated with them
    members: Mapped[list["Gymnast"]] = relationship(
        "Gymnast", back_populates="group", passive_deletes="all"
    )

    __table_args__ = (
        UniqueConstraint("club_id", "name", name="uq_group_name"),
    )


class MeetEntry(Base):
    """
    Represents a gymnast's entry into a specific meet,
    including details about the age group and level they are competing in.
    The Routine table will hold the apparatus-specific details for each entry.
    """

    __tablename__ = "meet_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    meet_id: Mapped[int] = mapped_column(Integer, ForeignKey("meets.id"), nullable=False)
    gymnast_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("gymnasts.id"), nullable=True)
    group_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("groups.id"), nullable=True)
    bib_number: Mapped[str] = mapped_column(String, nullable=False)
    entry_fee_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    age_group: Mapped[AgeGroup] = mapped_column(Enum(AgeGroup), nullable=False)
    level: Mapped[Level] = mapped_column(Enum(Level), nullable=False)

    meet: Mapped["Meet"] = relationship("Meet", back_populates="entries")
    gymnast: Mapped["Gymnast"] = relationship("Gymnast", back_populates="entries")
    routines: Mapped[list["Routine"]] = relationship(
        "Routine", back_populates="entry", cascade="all, delete-orphan"
    )
    group: Mapped["Group | None"] = relationship()

    __table_args__ = (
        UniqueConstraint("meet_id", "gymnast_id", name="uq_meet_entry_gymnast"),
        UniqueConstraint("meet_id", "group_id", name="uq_meet_entry_group"),
        CheckConstraint(
            "(gymnast_id IS NOT NULL AND group_id IS NULL) OR (group_id IS NOT NULL AND gymnast_id IS NULL)",
            name="ck_meet_entry_gymnast_or_group_not_null")
        )


class Routine(Base):
    """
    One row per apparatus per entry.
    """

    __tablename__ = "routines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    entry_id: Mapped[int] = mapped_column(Integer, ForeignKey("meet_entries.id"), nullable=False)
    apparatus: Mapped[Apparatus] = mapped_column(Enum(Apparatus), nullable=False)
    order_of_performance: Mapped[int] = mapped_column(Integer, nullable=True)
    music_url: Mapped[str | None] = mapped_column(String, nullable=True)

    entry: Mapped["MeetEntry"] = relationship("MeetEntry", back_populates="routines")

    @property
    def gymnast(self) -> Optional["Gymnast"]:
        return self.entry.gymnast if self.entry else None

    __table_args__ = (UniqueConstraint("entry_id", "apparatus", name="uq_entry_apparatus"),)
