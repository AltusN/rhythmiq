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
"""

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
    )
    entry_out = make_meet_entry(
        db_session,
        meet,
        gymnast=gymnast_out,
        level=Level.level_7,
        age_group=AgeGroup.under_14,
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
    )
    entry_partial = make_meet_entry(
        db_session,
        meet,
        gymnast=gymnast_partial,
        level=Level.level_5,
        age_group=AgeGroup.under_12,
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

    entry_lower_e = make_meet_entry(db_session, meet, gymnast=gymnast_lower_e)
    entry_higher_e = make_meet_entry(db_session, meet, gymnast=gymnast_higher_e)

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
