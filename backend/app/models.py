from datetime import date as date_type
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, object_session, relationship


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
    level_6 = "level_6"
    level_7 = "level_7"
    level_8 = "level_8"
    level_9 = "level_9"
    level_10 = "level_10"
    high_performance_1 = "high_performance_1"
    high_performance_2 = "high_performance_2"
    high_performance_3 = "high_performance_3"
    high_performance_4 = "high_performance_4"
    pre_junior = "pre_junior"
    junior = "junior"
    senior = "senior"
    olympic = "olympic"


class Panel(StrEnum):
    # Difficulty is split into two independently-judged subgroups per FIG's Code of
    # Points (DB: Difficulty of Body, DA: Difficulty of Apparatus) -- their scores are
    # summed, not averaged together, and neither is capped at 10 like artistry/execution.
    difficulty_body = "difficulty_body"
    difficulty_apparatus = "difficulty_apparatus"
    execution = "execution"
    artistry = "artistry"


class PenaltyJudgeRole(StrEnum):
    # Per FIG's Code of Points section 14, penalties are assessed by one of three
    # judge roles, not the D/A/E scoring panel. The specific ~19 penalty categories
    # (e.g. "boundary touch", "unauthorized apparatus retrieval") are deliberately not
    # modeled as a second enum -- they're free text on PenaltyRecord.description, since
    # that list can change between Code of Points editions while these three roles won't.
    time_judge = "time_judge"
    line_judge = "line_judge"
    responsible_judge = "responsible_judge"


# Models
class Judge(Base):
    __tablename__ = "judges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    last_name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(3), index=True, nullable=True)
    brevet: Mapped[str | None] = mapped_column(String, nullable=True)

    judge_scores: Mapped[list["JudgeScore"]] = relationship(
        "JudgeScore", back_populates="judge", passive_deletes=True
    )
    penalty_records: Mapped[list["PenaltyRecord"]] = relationship(
        "PenaltyRecord", back_populates="judge", passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint("first_name", "last_name", "country_code", name="uq_judge_identity"),
    )


class JudgeScore(Base):
    __tablename__ = "judge_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    routine_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("routines.id", ondelete="CASCADE"), nullable=False
    )
    judge_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("judges.id", ondelete="RESTRICT"), nullable=False
    )
    panel: Mapped[Panel] = mapped_column(Enum(Panel), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)

    routine: Mapped["Routine"] = relationship("Routine", back_populates="judge_scores")
    judge: Mapped["Judge"] = relationship("Judge", back_populates="judge_scores")

    __table_args__ = (
        UniqueConstraint(
            "routine_id", "judge_id", "panel", name="uq_judge_score_routine_judge_panel"
        ),
        CheckConstraint("value >= 0", name="ck_judge_score_value_non_negative"),
        CheckConstraint("value % 0.05 = 0", name="ck_judge_score_value_increments"),
        CheckConstraint(
            "panel IN ('difficulty_body', 'difficulty_apparatus') OR value <= 10",
            name="ck_judge_score_panel_value_cap",
        ),
    )


class PenaltyRecord(Base):
    """
    One itemized penalty deduction against a routine, per FIG's Code of Points section
    14. Unlike JudgeScore, deliberately has no UniqueConstraint -- the same judge_role
    can legitimately recur multiple times on one routine (e.g. two separate boundary
    touches by the Line judge).

    Routine.penalty is kept in sync with the sum of a routine's PenaltyRecords by
    app/routers/penalty_record.py's _resync_routine_penalty helper -- see that router's
    docstring for the guard that prevents the two from drifting apart.
    """

    __tablename__ = "penalty_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    routine_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("routines.id", ondelete="CASCADE"), nullable=False
    )
    judge_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("judges.id", ondelete="RESTRICT"), nullable=False
    )
    judge_role: Mapped[PenaltyJudgeRole] = mapped_column(Enum(PenaltyJudgeRole), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)

    routine: Mapped["Routine"] = relationship("Routine", back_populates="penalty_records")
    judge: Mapped["Judge"] = relationship("Judge", back_populates="penalty_records")

    __table_args__ = (
        # Stricter than JudgeScore.value's >= 0 -- an itemized penalty line shouldn't
        # ever be a zero-value entry, which also makes a separate non-negative
        # constraint redundant.
        CheckConstraint("amount > 0", name="ck_penalty_record_amount_positive"),
        CheckConstraint("amount % 0.05 = 0", name="ck_penalty_record_amount_increments"),
    )


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
    # Standard-based medal tiers (as opposed to competitive rank) for smaller meets:
    # a routine/all-around total >= medal_gold_min is gold, >= medal_silver_min is
    # silver, anything below that is bronze. Both null (the default) means the meet
    # isn't using cutoffs and results.py reports rank only. Set together or not at all --
    # see ck_meet_medal_cutoffs_valid.
    medal_gold_min: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    medal_silver_min: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)

    district: Mapped["District | None"] = relationship("District", back_populates="meets")

    entries: Mapped[list["MeetEntry"]] = relationship(
        "MeetEntry", back_populates="meet", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_meet_dates_valid"),
        CheckConstraint(
            "(medal_gold_min IS NULL) = (medal_silver_min IS NULL) "
            "AND (medal_gold_min IS NULL OR medal_gold_min > medal_silver_min)",
            name="ck_meet_medal_cutoffs_valid",
        ),
    )


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

    club: Mapped["Club | None"] = relationship("Club", back_populates="gymnasts")
    entries: Mapped[list["MeetEntry"]] = relationship(
        "MeetEntry", back_populates="gymnast", cascade="all, delete-orphan"
    )
    group: Mapped["Group | None"] = relationship("Group", back_populates="members")

    __table_args__ = (
        CheckConstraint("length(first_name) > 2", name="ck_gymnast_first_name_nonempty"),
        CheckConstraint("date_of_birth <= current_date", name="ck_gymnast_date_of_birth_valid"),
        UniqueConstraint("first_name", "last_name", "date_of_birth", name="uq_gymnast_identity"),
    )


class RoutineProfile(Base):
    """
    Represents a predefined routine profile for a specific gymnast or group.
    The music and choreography details can be stored here for reference during competitions."""

    __tablename__ = "routine_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    gymnast_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("gymnasts.id", ondelete="CASCADE"), nullable=True
    )
    group_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=True
    )
    apparatus: Mapped[Apparatus] = mapped_column(Enum(Apparatus), nullable=False)
    level: Mapped[Level] = mapped_column(Enum(Level), nullable=False)
    music_url: Mapped[str | None] = mapped_column(String, nullable=True)
    choreography_notes: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "gymnast_id", "apparatus", "level", name="uq_routine_profile_gymnast_apparatus_level"
        ),
        UniqueConstraint(
            "group_id", "apparatus", "level", name="uq_routine_profile_group_apparatus_level"
        ),
        CheckConstraint(
            "(gymnast_id IS NOT NULL AND group_id IS NULL) OR (group_id IS NOT NULL AND gymnast_id IS NULL)",
            name="ck_routine_profile_gymnast_or_group_not_null",
        ),
    )


class Group(Base):
    """
    Represents a group of gymnasts within a meet, typically based on age group and level.
    """

    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    club_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clubs.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, index=True, nullable=False)

    club: Mapped["Club"] = relationship("Club", back_populates="groups")
    # Restrict deletion of groups that have gymnasts associated with them
    members: Mapped[list["Gymnast"]] = relationship(
        "Gymnast", back_populates="group", passive_deletes="all"
    )

    __table_args__ = (UniqueConstraint("club_id", "name", name="uq_group_name"),)


class MeetEntry(Base):
    """
    Represents a gymnast's entry into a specific meet,
    including details about the age group and level they are competing in.
    The Routine table will hold the apparatus-specific details for each entry.
    """

    __tablename__ = "meet_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    meet_id: Mapped[int] = mapped_column(Integer, ForeignKey("meets.id"), nullable=False)
    gymnast_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("gymnasts.id"), nullable=True
    )
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
        UniqueConstraint("meet_id", "bib_number", name="uq_meet_entry_bib_number"),
        CheckConstraint(
            "(gymnast_id IS NOT NULL AND group_id IS NULL) OR (group_id IS NOT NULL AND gymnast_id IS NULL)",
            name="ck_meet_entry_gymnast_or_group_not_null",
        ),
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
    penalty: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), default=0, server_default="0", nullable=False
    )

    entry: Mapped["MeetEntry"] = relationship("MeetEntry", back_populates="routines")
    judge_scores: Mapped[list["JudgeScore"]] = relationship(
        "JudgeScore", back_populates="routine", cascade="all, delete-orphan"
    )
    penalty_records: Mapped[list["PenaltyRecord"]] = relationship(
        "PenaltyRecord", back_populates="routine", cascade="all, delete-orphan"
    )

    @property
    def gymnast(self) -> Gymnast | None:
        return self.entry.gymnast if self.entry else None

    @property
    def group(self) -> Group | None:
        return self.entry.group if self.entry else None

    @property
    def music_url(self) -> str | None:
        session = object_session(self)
        if session is None or self.entry is None:
            return None
        routine_profile = (
            session.query(RoutineProfile)
            .filter_by(
                gymnast_id=self.gymnast.id if self.gymnast else None,
                group_id=self.group.id if self.group else None,
                apparatus=self.apparatus,
                level=self.entry.level if self.entry else None,
            )
            .first()
        )
        return routine_profile.music_url if routine_profile else None

    __table_args__ = (
        UniqueConstraint("entry_id", "apparatus", name="uq_entry_apparatus"),
        CheckConstraint("penalty >= 0", name="ck_routine_penalty_non_negative"),
        CheckConstraint("penalty % 0.05 = 0", name="ck_routine_penalty_increments"),
    )
