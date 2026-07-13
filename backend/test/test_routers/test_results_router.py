"""
Test cases for the results router (/meets/{id}/standings, /meets/{id}/all-around).

Key points:
- Read-only reporting endpoints -- no POST/PATCH/DELETE to test.
- The ranking math itself (tie-breaks, shared ranks, partial-set handling) is unit-tested
  against SimpleNamespace stand-ins in test_scoring.py; these tests only need to prove the
  endpoints wire real ORM data through correctly (filters, provisional flag, 404s, name
  resolution for both gymnast and group entries).
- Builds one meet with several entries explicitly (rather than relying on make_routine's
  auto-built club/meet chain), so multiple entries can share one meet/level/age_group slice.
- `medal` is additive to `rank`: it's a standard-based tier from the meet's configured
  medal_gold_min/medal_silver_min, null on both endpoints when a meet isn't using cutoffs.
"""

from decimal import Decimal

from app.models import AgeGroup, Apparatus, Level, MeetStatus, Panel
from test.conftest import (
    make_group,
    make_gymnast,
    make_judge,
    make_judge_score,
    make_meet,
    make_meet_entry,
    make_routine,
)


##-- GET /meets/{id}/standings --##
def test_get_standings_orders_by_total_and_resolves_names(client, db_session):
    meet = make_meet(db_session, status=MeetStatus.scheduled)
    gymnast_a = make_gymnast(db_session, first_name="Anna", last_name="Petrov")
    gymnast_b = make_gymnast(db_session, first_name="Bella", last_name="Ivanova")
    group = make_group(db_session, club=gymnast_a.club, name="Junior Trio")

    entry_a = make_meet_entry(
        db_session,
        meet,
        gymnast=gymnast_a,
        level=Level.level_5,
        age_group=AgeGroup.under_12,
        bib_number="101",
    )
    entry_b = make_meet_entry(
        db_session,
        meet,
        gymnast=gymnast_b,
        level=Level.level_5,
        age_group=AgeGroup.under_12,
        bib_number="102",
    )
    entry_group = make_meet_entry(
        db_session,
        meet,
        group=group,
        level=Level.level_5,
        age_group=AgeGroup.under_12,
        bib_number="103",
    )

    routine_a = make_routine(db_session, entry_a, apparatus=Apparatus.ball)
    routine_b = make_routine(db_session, entry_b, apparatus=Apparatus.ball)
    routine_group = make_routine(db_session, entry_group, apparatus=Apparatus.ball)

    judge = make_judge(db_session)
    make_judge_score(
        db_session, routine=routine_a, judge=judge, panel=Panel.execution, value="8.00"
    )
    make_judge_score(
        db_session, routine=routine_b, judge=judge, panel=Panel.execution, value="9.00"
    )
    make_judge_score(
        db_session, routine=routine_group, judge=judge, panel=Panel.execution, value="7.00"
    )
    db_session.commit()

    response = client.get(
        f"/meets/{meet.id}/standings",
        params={"apparatus": "ball", "level": "level_5", "age_group": "u12"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provisional"] is True
    assert body["apparatus"] == "ball"
    rankings = body["rankings"]
    assert [row["rank"] for row in rankings] == [1, 2, 3]
    assert [row["routine_id"] for row in rankings] == [routine_b.id, routine_a.id, routine_group.id]
    assert rankings[0]["competitor_name"] == "Bella Ivanova"
    assert rankings[2]["competitor_name"] == "Junior Trio"


def test_get_standings_requires_apparatus(client, db_session):
    meet = make_meet(db_session)
    db_session.commit()

    response = client.get(f"/meets/{meet.id}/standings")

    assert response.status_code == 422


def test_get_standings_level_and_age_group_filter(client, db_session):
    meet = make_meet(db_session)
    gymnast_in = make_gymnast(db_session, first_name="Inna", last_name="Slice")
    gymnast_out = make_gymnast(db_session, first_name="Outa", last_name="Of Slice")

    entry_in = make_meet_entry(
        db_session,
        meet,
        gymnast=gymnast_in,
        level=Level.level_5,
        age_group=AgeGroup.under_12,
        bib_number="101",
    )
    entry_out = make_meet_entry(
        db_session,
        meet,
        gymnast=gymnast_out,
        level=Level.level_7,
        age_group=AgeGroup.under_14,
        bib_number="102",
    )
    routine_in = make_routine(db_session, entry_in, apparatus=Apparatus.hoop)
    make_routine(db_session, entry_out, apparatus=Apparatus.hoop)

    judge = make_judge(db_session)
    make_judge_score(
        db_session, routine=routine_in, judge=judge, panel=Panel.execution, value="8.00"
    )
    db_session.commit()

    response = client.get(
        f"/meets/{meet.id}/standings",
        params={"apparatus": "hoop", "level": "level_5", "age_group": "u12"},
    )

    assert response.status_code == 200
    rankings = response.json()["rankings"]
    assert len(rankings) == 1
    assert rankings[0]["routine_id"] == routine_in.id


def test_get_standings_provisional_false_for_completed_meet(client, db_session):
    meet = make_meet(db_session, status=MeetStatus.completed)
    entry = make_meet_entry(db_session, meet, gymnast=make_gymnast(db_session))
    make_routine(db_session, entry, apparatus=Apparatus.ball)
    db_session.commit()

    response = client.get(f"/meets/{meet.id}/standings", params={"apparatus": "ball"})

    assert response.status_code == 200
    assert response.json()["provisional"] is False


def test_get_standings_empty_category_returns_empty_rankings(client, db_session):
    meet = make_meet(db_session)
    db_session.commit()

    response = client.get(f"/meets/{meet.id}/standings", params={"apparatus": "ribbon"})

    assert response.status_code == 200
    assert response.json()["rankings"] == []


def test_get_standings_meet_not_found(client):
    response = client.get("/meets/9999/standings", params={"apparatus": "ball"})

    assert response.status_code == 404


def test_get_standings_medal_null_without_configured_cutoffs(client, db_session):
    meet = make_meet(db_session)  # medal_gold_min/medal_silver_min default to None
    entry = make_meet_entry(db_session, meet, gymnast=make_gymnast(db_session))
    routine = make_routine(db_session, entry, apparatus=Apparatus.ball)
    judge = make_judge(db_session)
    make_judge_score(db_session, routine=routine, judge=judge, panel=Panel.execution, value="9.00")
    db_session.commit()

    response = client.get(f"/meets/{meet.id}/standings", params={"apparatus": "ball"})

    assert response.status_code == 200
    assert response.json()["rankings"][0]["medal"] is None


def test_get_standings_medal_tiers_from_configured_cutoffs(client, db_session):
    # gold_min/silver_min apply uniformly across the meet, independent of rank --
    # two different ranks can both land in "gold" here.
    meet = make_meet(db_session, medal_gold_min=Decimal("8.50"), medal_silver_min=Decimal("6.00"))
    gymnast_gold = make_gymnast(db_session, first_name="Top", last_name="Scorer")
    gymnast_also_gold = make_gymnast(db_session, first_name="Second", last_name="Scorer")
    gymnast_bronze = make_gymnast(db_session, first_name="Low", last_name="Scorer")

    entry_gold = make_meet_entry(db_session, meet, gymnast=gymnast_gold, bib_number="101")
    entry_also_gold = make_meet_entry(db_session, meet, gymnast=gymnast_also_gold, bib_number="102")
    entry_bronze = make_meet_entry(db_session, meet, gymnast=gymnast_bronze, bib_number="103")

    routine_gold = make_routine(db_session, entry_gold, apparatus=Apparatus.ball)
    routine_also_gold = make_routine(db_session, entry_also_gold, apparatus=Apparatus.ball)
    routine_bronze = make_routine(db_session, entry_bronze, apparatus=Apparatus.ball)

    judge = make_judge(db_session)
    make_judge_score(
        db_session, routine=routine_gold, judge=judge, panel=Panel.execution, value="9.50"
    )
    make_judge_score(
        db_session, routine=routine_also_gold, judge=judge, panel=Panel.execution, value="9.00"
    )
    make_judge_score(
        db_session, routine=routine_bronze, judge=judge, panel=Panel.execution, value="5.00"
    )
    db_session.commit()

    response = client.get(f"/meets/{meet.id}/standings", params={"apparatus": "ball"})

    assert response.status_code == 200
    by_routine = {row["routine_id"]: row for row in response.json()["rankings"]}

    assert by_routine[routine_gold.id]["rank"] == 1
    assert by_routine[routine_gold.id]["medal"] == "gold"
    assert by_routine[routine_also_gold.id]["rank"] == 2
    assert by_routine[routine_also_gold.id]["medal"] == "gold"
    assert by_routine[routine_bronze.id]["rank"] == 3
    assert by_routine[routine_bronze.id]["medal"] == "bronze"


##-- GET /meets/{id}/all-around --##
def test_get_all_around_sums_across_apparatus_and_ranks(client, db_session):
    meet = make_meet(db_session, status=MeetStatus.scheduled)
    gymnast_complete = make_gymnast(db_session, first_name="Complete", last_name="Set")
    gymnast_partial = make_gymnast(db_session, first_name="Partial", last_name="Set")

    entry_complete = make_meet_entry(
        db_session,
        meet,
        gymnast=gymnast_complete,
        level=Level.level_5,
        age_group=AgeGroup.under_12,
        bib_number="101",
    )
    entry_partial = make_meet_entry(
        db_session,
        meet,
        gymnast=gymnast_partial,
        level=Level.level_5,
        age_group=AgeGroup.under_12,
        bib_number="102",
    )

    ball_complete = make_routine(db_session, entry_complete, apparatus=Apparatus.ball)
    hoop_complete = make_routine(db_session, entry_complete, apparatus=Apparatus.hoop)
    ball_partial = make_routine(db_session, entry_partial, apparatus=Apparatus.ball)

    judge = make_judge(db_session)
    make_judge_score(
        db_session, routine=ball_complete, judge=judge, panel=Panel.execution, value="8.00"
    )
    make_judge_score(
        db_session, routine=hoop_complete, judge=judge, panel=Panel.execution, value="8.00"
    )
    make_judge_score(
        db_session, routine=ball_partial, judge=judge, panel=Panel.execution, value="9.50"
    )
    db_session.commit()

    response = client.get(
        f"/meets/{meet.id}/all-around", params={"level": "level_5", "age_group": "u12"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provisional"] is True
    rankings = body["rankings"]
    by_entry = {row["entry_id"]: row for row in rankings}

    assert by_entry[entry_complete.id]["total"] == "16.00"
    assert by_entry[entry_complete.id]["routines_counted"] == 2
    assert by_entry[entry_complete.id]["rank"] == 1

    assert by_entry[entry_partial.id]["total"] == "9.50"
    assert by_entry[entry_partial.id]["routines_counted"] == 1
    assert by_entry[entry_partial.id]["rank"] == 2


def test_get_all_around_execution_tiebreak_on_equal_totals(client, db_session):
    meet = make_meet(db_session)
    gymnast_lower_e = make_gymnast(db_session, first_name="Lower", last_name="Execution")
    gymnast_higher_e = make_gymnast(db_session, first_name="Higher", last_name="Execution")

    entry_lower_e = make_meet_entry(db_session, meet, gymnast=gymnast_lower_e, bib_number="101")
    entry_higher_e = make_meet_entry(db_session, meet, gymnast=gymnast_higher_e, bib_number="102")

    routine_lower_e = make_routine(db_session, entry_lower_e, apparatus=Apparatus.ball)
    routine_higher_e = make_routine(db_session, entry_higher_e, apparatus=Apparatus.ball)

    judge = make_judge(db_session)
    make_judge_score(
        db_session, routine=routine_lower_e, judge=judge, panel=Panel.difficulty_body, value="10.00"
    )
    make_judge_score(
        db_session, routine=routine_lower_e, judge=judge, panel=Panel.artistry, value="5.00"
    )
    make_judge_score(
        db_session, routine=routine_lower_e, judge=judge, panel=Panel.execution, value="5.00"
    )
    make_judge_score(
        db_session, routine=routine_higher_e, judge=judge, panel=Panel.difficulty_body, value="8.00"
    )
    make_judge_score(
        db_session, routine=routine_higher_e, judge=judge, panel=Panel.artistry, value="5.00"
    )
    make_judge_score(
        db_session, routine=routine_higher_e, judge=judge, panel=Panel.execution, value="7.00"
    )
    db_session.commit()

    response = client.get(f"/meets/{meet.id}/all-around")

    assert response.status_code == 200
    rankings = response.json()["rankings"]
    by_entry = {row["entry_id"]: row for row in rankings}
    assert by_entry[entry_lower_e.id]["total"] == by_entry[entry_higher_e.id]["total"] == "20.00"
    assert by_entry[entry_higher_e.id]["rank"] == 1
    assert by_entry[entry_lower_e.id]["rank"] == 2


def test_get_all_around_provisional_false_for_completed_meet(client, db_session):
    meet = make_meet(db_session, status=MeetStatus.completed)
    entry = make_meet_entry(db_session, meet, gymnast=make_gymnast(db_session))
    make_routine(db_session, entry, apparatus=Apparatus.ball)
    db_session.commit()

    response = client.get(f"/meets/{meet.id}/all-around")

    assert response.status_code == 200
    assert response.json()["provisional"] is False


def test_get_all_around_meet_not_found(client):
    response = client.get("/meets/9999/all-around")

    assert response.status_code == 404


def test_get_all_around_medal_null_without_configured_cutoffs(client, db_session):
    meet = make_meet(db_session)
    entry = make_meet_entry(db_session, meet, gymnast=make_gymnast(db_session))
    routine = make_routine(db_session, entry, apparatus=Apparatus.ball)
    judge = make_judge(db_session)
    make_judge_score(db_session, routine=routine, judge=judge, panel=Panel.execution, value="9.00")
    db_session.commit()

    response = client.get(f"/meets/{meet.id}/all-around")

    assert response.status_code == 200
    assert response.json()["rankings"][0]["medal"] is None


def test_get_all_around_medal_tiers_from_configured_cutoffs(client, db_session):
    # gold_min/silver_min apply to the summed all-around total, not a single
    # apparatus's execution mark (which is capped at 10 per ck_judge_score_panel_value_cap).
    meet = make_meet(db_session, medal_gold_min=Decimal("16.00"), medal_silver_min=Decimal("10.00"))
    gymnast_silver = make_gymnast(db_session, first_name="Mid", last_name="Scorer")
    gymnast_bronze = make_gymnast(db_session, first_name="Low", last_name="Scorer")

    entry_silver = make_meet_entry(db_session, meet, gymnast=gymnast_silver, bib_number="101")
    entry_bronze = make_meet_entry(db_session, meet, gymnast=gymnast_bronze, bib_number="102")

    ball_silver = make_routine(db_session, entry_silver, apparatus=Apparatus.ball)
    hoop_silver = make_routine(db_session, entry_silver, apparatus=Apparatus.hoop)
    routine_bronze = make_routine(db_session, entry_bronze, apparatus=Apparatus.ball)

    judge = make_judge(db_session)
    make_judge_score(
        db_session, routine=ball_silver, judge=judge, panel=Panel.execution, value="8.00"
    )
    make_judge_score(
        db_session, routine=hoop_silver, judge=judge, panel=Panel.execution, value="7.00"
    )
    make_judge_score(
        db_session, routine=routine_bronze, judge=judge, panel=Panel.execution, value="5.00"
    )
    db_session.commit()

    response = client.get(f"/meets/{meet.id}/all-around")

    assert response.status_code == 200
    by_entry = {row["entry_id"]: row for row in response.json()["rankings"]}

    assert by_entry[entry_silver.id]["medal"] == "silver"
    assert by_entry[entry_bronze.id]["medal"] == "bronze"
