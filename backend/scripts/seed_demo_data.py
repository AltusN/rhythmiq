"""Populate the active database with a broad, varied demo dataset.

Targets whatever POSTGRESQL_DATABASE_URL is active (see app/db.py). Not idempotent by
design: run it once against a freshly migrated database (`make dev && make seed`), and
use `make reset` to wipe and start over rather than re-running this against a populated DB.

Goal is BREADTH: every table populated, and within each table the meaningful variations
covered rather than just a couple of rows. Specifically it guarantees:

- every MeetStatus, including a cancelled meet and a meet with no district
- every AgeGroup value, across both the u7-o11 and the older u12/u14/o14 bandings
- every Apparatus
- every Panel (difficulty_body, difficulty_apparatus, execution, artistry)
- every PenaltyJudgeRole
- every Ethnicity value, plus gymnasts with none recorded
- gymnasts with and without a club, with and without a group, with and without a
  gsa_number and country_code
- meets with and without medal cutoffs
- routines fully scored (completed meet), partially scored (in progress) and unscored

Scoring note: `scoring.py` uses TRIM_THRESHOLD = 4 -- with 4 or more marks `trimmed_mean`
discards the highest and lowest; with fewer it returns the plain average, and only an
empty panel yields 0. (Note scoring.py's own docstring wrongly claims it returns 0 below
the threshold -- the code does not.) Every scored panel here gets 4 marks so the trimming
path itself is exercised.

Caveat worth knowing: the app's judge panel UI models a SMALL panel -- one D judge
covering both difficulty subgroups, four E judges, one A judge -- so in real use D-Body,
D-App and artistry each receive a single mark and take the plain-average path. This seed
deliberately populates 4 marks per panel to exercise trimming, which means it is not a
faithful reproduction of what the panel UI can produce.

Randomness is seeded with a fixed value, so repeated runs against a fresh database produce
identical data.
"""

import random
from datetime import date
from decimal import Decimal

from app.db import SessionLocal
from app.models import (
    AgeGroup,
    Apparatus,
    Club,
    Coach,
    District,
    Ethnicity,
    Group,
    Gymnast,
    Judge,
    JudgeScore,
    Level,
    Meet,
    MeetEntry,
    MeetStatus,
    Panel,
    PenaltyJudgeRole,
    PenaltyRecord,
    Routine,
    RoutineProfile,
)

SEED = 20260720

# (first, last, birth year, club key or None, group key or None, ethnicity, gsa number)
# Deliberately spans the optional-field space: unaffiliated gymnasts, gymnasts with no
# ethnicity recorded (NULL, distinct from prefer_not_to_say), and gymnasts with no GSA
# number. Every Ethnicity member appears at least twice.
GYMNASTS = [
    ("Anna", "Petrov", 2012, "star", "star_junior", Ethnicity.white, "GSA-10001"),
    ("Maya", "Chen", 2012, "star", "star_junior", Ethnicity.indian, "GSA-10002"),
    ("Lerato", "Mokoena", 2013, "star", "star_junior", Ethnicity.black, "GSA-10003"),
    ("Zanele", "Dlamini", 2013, "star", "star_junior", Ethnicity.black, None),
    ("Chloe", "Fourie", 2014, "star", None, Ethnicity.white, "GSA-10005"),
    ("Amara", "Nkosi", 2015, "star", None, Ethnicity.black, "GSA-10006"),
    ("Sasha", "Eburne", 2010, "auro", "auro_senior", Ethnicity.coloured, "GSA-10007"),
    ("Tania", "Zovitzkey", 2010, "auro", "auro_senior", Ethnicity.white, "GSA-10008"),
    ("Priya", "Naidoo", 2011, "auro", "auro_senior", Ethnicity.indian, "GSA-10009"),
    ("Kira", "Volkova", 2011, "auro", None, Ethnicity.white, None),
    ("Nadia", "Abrahams", 2016, "auro", None, Ethnicity.coloured, "GSA-10011"),
    ("Olivia", "Bester", 2017, "auro", None, None, None),
    ("Megan", "Fox", 2009, "rivr", None, Ethnicity.white, "GSA-10013"),
    ("Thandiwe", "Zulu", 2009, "rivr", None, Ethnicity.black, "GSA-10014"),
    ("Ruby", "Adams", 2014, "rivr", None, Ethnicity.prefer_not_to_say, "GSA-10015"),
    ("Sana", "Patel", 2015, "rivr", None, Ethnicity.indian, None),
    ("Elsa", "Jordaan", 2018, "rivr", None, Ethnicity.white, None),
    ("Aaliyah", "Daniels", 2019, "rivr", None, Ethnicity.coloured, "GSA-10018"),
    ("Lindiwe", "Khumalo", 2012, "brit", "brit_junior", Ethnicity.black, "GSA-10019"),
    ("Marike", "van Wyk", 2012, "brit", "brit_junior", Ethnicity.white, "GSA-10020"),
    ("Shanice", "Peters", 2013, "brit", "brit_junior", Ethnicity.coloured, None),
    ("Divya", "Reddy", 2016, "brit", None, Ethnicity.indian, "GSA-10022"),
    ("Emma", "Kruger", 2017, "brit", None, None, None),
    ("Palesa", "Molefe", 2019, "held", None, Ethnicity.black, "GSA-10024"),
    ("Sofia", "Botha", 2020, "held", None, Ethnicity.white, None),
    ("Ayesha", "Cassim", 2018, "held", None, Ethnicity.indian, "GSA-10026"),
    ("Refilwe", "Sithole", 2011, "gcrg", "gcrg_senior", Ethnicity.black, "GSA-10027"),
    ("Hannah", "Meyer", 2010, "gcrg", "gcrg_senior", Ethnicity.prefer_not_to_say, "GSA-10028"),
    # Unaffiliated: club_id NULL is a supported state (see the Gymnast docstring).
    ("Isabel", "Ferreira", 2013, None, None, Ethnicity.white, "GSA-10029"),
    ("Nomsa", "Mahlangu", 2014, None, None, Ethnicity.black, None),
]

# (first, last, country, brevet). Brevet is free text by design (Phase 2b spec), so the
# notation here is kept CONSISTENT rather than mirroring the drift seen in live data.
JUDGES = [
    ("Naledi", "Dlamini", "RSA", "Cat I"),
    ("Elena", "Petrova", "BUL", "Cat I"),
    ("Yuki", "Tanaka", "JPN", "Cat II"),
    ("Sofia", "Rossi", "ITA", "Cat II"),
    ("Annette", "Povlova", "RSA", "Cat III"),
    ("Zoey", "Botha", "USA", "Cat III"),
    ("Carla", "Mendes", "ESP", None),
    ("Oksana", "Bondar", "UKR", "Cat IV"),
]


def _mark(rng: random.Random, low: str, high: str) -> Decimal:
    """A judge mark in [low, high], on the 0.05 increments the CheckConstraints require."""
    steps = int((Decimal(high) - Decimal(low)) / Decimal("0.05"))
    return (Decimal(low) + Decimal("0.05") * rng.randint(0, steps)).quantize(Decimal("0.01"))


def _score_routine(db, rng: random.Random, routine: Routine, judges: list[Judge]) -> None:
    """
    Give a routine a full set of marks: 4 per panel, which is what TRIM_THRESHOLD needs.

    Difficulty is uncapped; execution and artistry are capped at 10 by
    ck_judge_score_panel_value_cap.
    """
    panels = [
        (Panel.difficulty_body, judges[0:4], "2.50", "6.00"),
        (Panel.difficulty_apparatus, judges[0:4], "2.00", "5.50"),
        (Panel.execution, judges[4:8], "6.00", "9.50"),
        (Panel.artistry, judges[4:8], "6.50", "9.50"),
    ]
    for panel, panel_judges, low, high in panels:
        for judge in panel_judges:
            db.add(
                JudgeScore(
                    routine_id=routine.id,
                    judge_id=judge.id,
                    panel=panel,
                    value=_mark(rng, low, high),
                )
            )


def run() -> None:
    rng = random.Random(SEED)
    db = SessionLocal()
    try:
        # -- Districts --
        districts = {
            "wp": District(name="Western Province", abbreviation="WP"),
            "bol": District(name="Boland", abbreviation="BOL"),
            "gau": District(name="Gauteng", abbreviation="GAU"),
        }
        db.add_all(districts.values())
        db.flush()

        # -- Clubs: several per district, so the club filters have something to filter --
        clubs = {
            "star": Club(
                district_id=districts["wp"].id,
                name="Starlight Gymnastics",
                abbreviation="STAR",
            ),
            "auro": Club(
                district_id=districts["wp"].id, name="Aurora Rhythmic", abbreviation="AURO"
            ),
            "rivr": Club(
                district_id=districts["wp"].id,
                name="Riverside Gymnastics Club",
                abbreviation="RIVR",
            ),
            "brit": Club(
                district_id=districts["bol"].id,
                name="Boland Ritmiese Klub",
                abbreviation="BRIT",
            ),
            "held": Club(
                district_id=districts["bol"].id, name="Helderberg RG", abbreviation="HELD"
            ),
            "gcrg": Club(
                district_id=districts["gau"].id,
                name="Gauteng Central RG",
                abbreviation="GCRG",
            ),
        }
        db.add_all(clubs.values())
        db.flush()

        # -- Coaches: head + assistant for most clubs; "held" deliberately has none --
        db.add_all(
            [
                Coach(
                    club_id=clubs["star"].id,
                    first_name="Elena",
                    last_name="Volkova",
                    is_head_coach=True,
                ),
                Coach(
                    club_id=clubs["star"].id,
                    first_name="Pieter",
                    last_name="Marais",
                    is_head_coach=False,
                ),
                Coach(
                    club_id=clubs["auro"].id,
                    first_name="Nomvula",
                    last_name="Ndlovu",
                    is_head_coach=True,
                ),
                Coach(
                    club_id=clubs["auro"].id,
                    first_name="Jana",
                    last_name="de Villiers",
                    is_head_coach=False,
                ),
                Coach(
                    club_id=clubs["rivr"].id,
                    first_name="Fatima",
                    last_name="Ismail",
                    is_head_coach=True,
                ),
                Coach(
                    club_id=clubs["brit"].id,
                    first_name="Anli",
                    last_name="Steyn",
                    is_head_coach=True,
                ),
                Coach(
                    club_id=clubs["brit"].id,
                    first_name="Sipho",
                    last_name="Mthembu",
                    is_head_coach=False,
                ),
                Coach(
                    club_id=clubs["gcrg"].id,
                    first_name="Rina",
                    last_name="Coetzee",
                    is_head_coach=True,
                ),
            ]
        )

        # -- Groups --
        groups = {
            "star_junior": Group(club_id=clubs["star"].id, name="Starlight Junior Ensemble"),
            "auro_senior": Group(club_id=clubs["auro"].id, name="Aurora Senior Ensemble"),
            "brit_junior": Group(club_id=clubs["brit"].id, name="Boland Junior Ensemble"),
            "gcrg_senior": Group(club_id=clubs["gcrg"].id, name="Gauteng Senior Ensemble"),
        }
        db.add_all(groups.values())
        db.flush()

        # -- Gymnasts --
        gymnasts: dict[str, Gymnast] = {}
        for first, last, birth_year, club_key, group_key, ethnicity, gsa in GYMNASTS:
            gymnast = Gymnast(
                club_id=clubs[club_key].id if club_key else None,
                group_id=groups[group_key].id if group_key else None,
                first_name=first,
                last_name=last,
                date_of_birth=date(birth_year, rng.randint(1, 12), rng.randint(1, 28)),
                # A few have no country recorded; the rest are mostly RSA.
                country_code=None if gsa is None and club_key is None else "RSA",
                ethnicity=ethnicity,
                gsa_number=gsa,
            )
            gymnasts[f"{first} {last}"] = gymnast
        db.add_all(gymnasts.values())
        db.flush()

        # -- Judges --
        judges = [
            Judge(first_name=first, last_name=last, country_code=country, brevet=brevet)
            for first, last, country, brevet in JUDGES
        ]
        db.add_all(judges)
        db.flush()

        # -- Meets: one of every MeetStatus --
        meet_completed = Meet(
            district_id=districts["wp"].id,
            name="Spring Open",
            location="Riverside Gymnasium",
            start_date=date(2026, 4, 18),
            end_date=date(2026, 4, 19),
            status=MeetStatus.completed,
            # Medal cutoffs exercise medal_for_total in scoring.py. Both or neither, and
            # gold must exceed silver (ck_meet_medal_cutoffs_valid).
            medal_gold_min=Decimal("24.00"),
            medal_silver_min=Decimal("21.00"),
        )
        meet_in_progress = Meet(
            district_id=districts["bol"].id,
            name="Boland Championship",
            location="Helderberg Sports Hall",
            start_date=date(2026, 7, 24),
            end_date=date(2026, 7, 26),
            status=MeetStatus.in_progress,
            medal_gold_min=Decimal("23.50"),
            medal_silver_min=Decimal("20.00"),
        )
        meet_scheduled = Meet(
            district_id=districts["gau"].id,
            name="Winter Classic",
            location="Gauteng Central Arena",
            start_date=date(2026, 9, 12),
            end_date=date(2026, 9, 13),
            status=MeetStatus.scheduled,
        )
        meet_draft = Meet(
            district_id=districts["wp"].id,
            name="Autumn Invitational",
            location="Starlight Arena",
            start_date=date(2026, 10, 3),
            end_date=date(2026, 10, 4),
            status=MeetStatus.draft,
        )
        # No district (the SET NULL case) and cancelled.
        meet_cancelled = Meet(
            district_id=None,
            name="Regional Qualifier",
            location="TBD",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 2),
            status=MeetStatus.cancelled,
        )
        db.add_all([meet_completed, meet_in_progress, meet_scheduled, meet_draft, meet_cancelled])
        db.flush()

        # -- Meet entries --
        # (meet, owner name or group key, bib, age group, level, is_group)
        # Age groups deliberately span all nine values across both bandings.
        entry_plan = [
            # Spring Open (completed) -- fully scored below.
            (meet_completed, "Anna Petrov", "101", AgeGroup.under_12, Level.level_4, False),
            (meet_completed, "Maya Chen", "102", AgeGroup.under_12, Level.level_4, False),
            (meet_completed, "Lerato Mokoena", "103", AgeGroup.under_12, Level.level_3, False),
            (meet_completed, "Sasha Eburne", "104", AgeGroup.under_14, Level.level_6, False),
            (meet_completed, "Tania Zovitzkey", "105", AgeGroup.under_14, Level.level_6, False),
            (meet_completed, "Priya Naidoo", "106", AgeGroup.under_14, Level.level_5, False),
            (meet_completed, "Megan Fox", "107", AgeGroup.over_14, Level.senior, False),
            (meet_completed, "Thandiwe Zulu", "108", AgeGroup.over_14, Level.senior, False),
            (meet_completed, "Chloe Fourie", "109", AgeGroup.under_11, Level.level_2, False),
            (meet_completed, "Amara Nkosi", "110", AgeGroup.under_11, Level.level_2, False),
            (meet_completed, "star_junior", "G01", AgeGroup.under_12, Level.level_3, True),
            (meet_completed, "auro_senior", "G02", AgeGroup.over_14, Level.senior, True),
            # Boland Championship (in progress) -- partially scored below.
            (meet_in_progress, "Lindiwe Khumalo", "201", AgeGroup.under_12, Level.level_4, False),
            (meet_in_progress, "Marike van Wyk", "202", AgeGroup.under_12, Level.level_4, False),
            (meet_in_progress, "Shanice Peters", "203", AgeGroup.under_11, Level.level_3, False),
            (meet_in_progress, "Divya Reddy", "204", AgeGroup.under_10, Level.level_2, False),
            (meet_in_progress, "Emma Kruger", "205", AgeGroup.under_9, Level.level_1, False),
            (meet_in_progress, "Palesa Molefe", "206", AgeGroup.under_7, Level.level_1, False),
            (meet_in_progress, "Sofia Botha", "207", AgeGroup.under_7, Level.level_1, False),
            (meet_in_progress, "Ayesha Cassim", "208", AgeGroup.under_8, Level.level_1, False),
            (meet_in_progress, "brit_junior", "G11", AgeGroup.under_12, Level.level_3, True),
            (meet_in_progress, "gcrg_senior", "G12", AgeGroup.over_11, Level.junior, True),
            # Winter Classic (scheduled) -- entered, nothing scored.
            (meet_scheduled, "Refilwe Sithole", "301", AgeGroup.over_11, Level.junior, False),
            (meet_scheduled, "Hannah Meyer", "302", AgeGroup.over_14, Level.senior, False),
            (meet_scheduled, "Nadia Abrahams", "303", AgeGroup.under_10, Level.level_2, False),
            (meet_scheduled, "Olivia Bester", "304", AgeGroup.under_9, Level.level_1, False),
            (meet_scheduled, "Isabel Ferreira", "305", AgeGroup.under_12, Level.level_3, False),
            (meet_scheduled, "Nomsa Mahlangu", "306", AgeGroup.under_11, Level.level_2, False),
            # Autumn Invitational (draft).
            (meet_draft, "Ruby Adams", "401", AgeGroup.under_11, Level.level_2, False),
            (meet_draft, "Sana Patel", "402", AgeGroup.under_10, Level.level_2, False),
            (meet_draft, "Elsa Jordaan", "403", AgeGroup.under_8, Level.level_1, False),
            # Regional Qualifier (cancelled).
            (meet_cancelled, "Aaliyah Daniels", "501", AgeGroup.under_7, Level.level_1, False),
            (meet_cancelled, "Kira Volkova", "502", AgeGroup.under_14, Level.level_5, False),
        ]
        entries: list[tuple[MeetEntry, Meet]] = []
        for meet, owner_key, bib, age_group, level, is_group in entry_plan:
            entry = MeetEntry(
                meet_id=meet.id,
                gymnast_id=None if is_group else gymnasts[owner_key].id,
                group_id=groups[owner_key].id if is_group else None,
                bib_number=bib,
                age_group=age_group,
                level=level,
            )
            entries.append((entry, meet))
            db.add(entry)
        db.flush()

        # -- Routine profiles: gymnast-scoped and group-scoped --
        # Several deliberately match an entry's (owner, apparatus, level) so that
        # Routine.music_url resolves live; others do not, so the unresolved case shows too.
        db.add_all(
            [
                RoutineProfile(
                    gymnast_id=gymnasts["Anna Petrov"].id,
                    apparatus=Apparatus.ball,
                    level=Level.level_4,
                    music_url="https://example.com/music/anna-ball.mp3",
                    choreography_notes="Lyrical opening, tempo increases at 0:45.",
                ),
                RoutineProfile(
                    gymnast_id=gymnasts["Anna Petrov"].id,
                    apparatus=Apparatus.hoop,
                    level=Level.level_4,
                    music_url="https://example.com/music/anna-hoop.mp3",
                ),
                RoutineProfile(
                    gymnast_id=gymnasts["Maya Chen"].id,
                    apparatus=Apparatus.ball,
                    level=Level.level_4,
                    music_url="https://example.com/music/maya-ball.mp3",
                    choreography_notes="Pivot series at 1:05; ends on apparatus catch.",
                ),
                RoutineProfile(
                    gymnast_id=gymnasts["Sasha Eburne"].id,
                    apparatus=Apparatus.ribbon,
                    level=Level.level_6,
                    music_url="https://example.com/music/sasha-ribbon.mp3",
                ),
                RoutineProfile(
                    gymnast_id=gymnasts["Megan Fox"].id,
                    apparatus=Apparatus.clubs,
                    level=Level.senior,
                    music_url="https://example.com/music/megan-clubs.mp3",
                    choreography_notes="Risk element at 1:20.",
                ),
                RoutineProfile(
                    gymnast_id=gymnasts["Lindiwe Khumalo"].id,
                    apparatus=Apparatus.hoop,
                    level=Level.level_4,
                    music_url="https://example.com/music/lindiwe-hoop.mp3",
                ),
                RoutineProfile(
                    group_id=groups["star_junior"].id,
                    apparatus=Apparatus.clubs,
                    level=Level.level_3,
                    music_url="https://example.com/music/starlight-junior-clubs.mp3",
                    choreography_notes="Synchronised exchange at centre; formation change at 1:10.",
                ),
                RoutineProfile(
                    group_id=groups["auro_senior"].id,
                    apparatus=Apparatus.freehand,
                    level=Level.senior,
                    music_url="https://example.com/music/aurora-senior-freehand.mp3",
                ),
                RoutineProfile(
                    group_id=groups["brit_junior"].id,
                    apparatus=Apparatus.rope,
                    level=Level.level_3,
                    music_url="https://example.com/music/boland-junior-rope.mp3",
                ),
            ]
        )

        # -- Routines --
        # Completed meet: two apparatus per entry, all fully scored.
        # In-progress meet: one apparatus per entry, only the first six scored, so the
        # half-finished state is visible on the scoring screen.
        # Scheduled meet: routines exist but carry no marks. Draft/cancelled: none.
        completed_apparatus = [Apparatus.ball, Apparatus.ribbon]
        in_progress_apparatus = [
            Apparatus.hoop,
            Apparatus.rope,
            Apparatus.clubs,
            Apparatus.freehand,
            Apparatus.ball,
            Apparatus.ribbon,
            Apparatus.hoop,
            Apparatus.rope,
            Apparatus.clubs,
            Apparatus.freehand,
        ]
        scored_routines: list[Routine] = []
        in_progress_index = 0

        for entry, meet in entries:
            if meet is meet_completed:
                for order, apparatus in enumerate(completed_apparatus, start=1):
                    routine = Routine(
                        entry_id=entry.id, apparatus=apparatus, order_of_performance=order
                    )
                    db.add(routine)
                    scored_routines.append(routine)
            elif meet is meet_in_progress:
                apparatus = in_progress_apparatus[in_progress_index % len(in_progress_apparatus)]
                routine = Routine(entry_id=entry.id, apparatus=apparatus, order_of_performance=1)
                db.add(routine)
                if in_progress_index < 6:
                    scored_routines.append(routine)
                in_progress_index += 1
            elif meet is meet_scheduled:
                db.add(Routine(entry_id=entry.id, apparatus=Apparatus.ball, order_of_performance=1))
        db.flush()

        # -- Judge scores: 4 marks per panel, per scored routine --
        for routine in scored_routines:
            _score_routine(db, rng, routine, judges)
        db.flush()

        # -- Penalty records: every PenaltyJudgeRole represented --
        # Routine.penalty is an aggregate the API keeps equal to the sum of a routine's
        # records (see routers/penalty_record.py). Seeding both directly means setting it
        # here by hand, or the invariant would be violated from the outset.
        penalty_plan = [
            (0, PenaltyJudgeRole.line_judge, "Apparatus out of bounds", Decimal("0.30")),
            (1, PenaltyJudgeRole.time_judge, "Routine under time", Decimal("0.05")),
            (2, PenaltyJudgeRole.responsible_judge, "Late presentation to floor", Decimal("0.50")),
            (3, PenaltyJudgeRole.line_judge, "Gymnast stepped outside area", Decimal("0.30")),
            (4, PenaltyJudgeRole.time_judge, "Routine over time", Decimal("0.10")),
            (5, PenaltyJudgeRole.responsible_judge, "Incorrect leotard", Decimal("0.30")),
        ]
        for index, role, description, amount in penalty_plan:
            routine = scored_routines[index]
            db.add(
                PenaltyRecord(
                    routine_id=routine.id,
                    judge_id=judges[4].id,
                    judge_role=role,
                    description=description,
                    amount=amount,
                )
            )
            routine.penalty = amount

        db.commit()
        print(
            f"Demo data seeded: {len(GYMNASTS)} gymnasts, {len(JUDGES)} judges, "
            f"{len(entry_plan)} entries, {len(scored_routines)} scored routines."
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
