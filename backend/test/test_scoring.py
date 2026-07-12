"""
Unit tests for app/scoring.py, using plain SimpleNamespace stand-ins for Routine/
JudgeScore rather than the DB, since the scoring math has no DB dependency.
- trimmed_mean: plain average below TRIM_THRESHOLD, trims high/low at or above it.
- compute_routine_score: D score is difficulty_body + difficulty_apparatus summed
  (not pooled and averaged like A/E), missing panels score 0, results are rounded to
  2 decimal places, penalty subtracts from the total, and D is not capped at 10 unlike
  A/E.
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models import Level, Panel
from app.scoring import (
    AllAroundStanding,
    ApparatusStanding,
    RoutineScoreResult,
    compute_routine_score,
    is_panel_valid_for_level,
    rank_all_around,
    rank_apparatus,
    trimmed_mean,
)


@pytest.mark.parametrize(
    "scores, expected",
    [
        ([Decimal("8.80"), Decimal("9.50"), Decimal("7.20")], Decimal("8.50")),
        ([Decimal("7.90"), Decimal("8.30")], Decimal("8.10")),
        ([Decimal("9.05")], Decimal("9.05")),
        ([], Decimal("0")),
        (
            [
                Decimal("7.80"),
                Decimal("7.95"),
                Decimal("8.05"),
                Decimal("8.10"),
                Decimal("8.20"),
                Decimal("9.00"),
            ],
            Decimal("8.075"),
        ),
    ],
)
def test_trimmed_mean(scores, expected):
    assert trimmed_mean(scores) == expected


def _mark(panel, value):
    return SimpleNamespace(panel=panel, value=Decimal(value))


def _routine(marks, penalty="0"):
    return SimpleNamespace(judge_scores=marks, penalty=Decimal(penalty))


def test_compute_routine_score_with_no_marks_returns_zero_scores():
    result = compute_routine_score(_routine([]))

    assert result.d_score == Decimal("0.00")
    assert result.a_score == Decimal("0.00")
    assert result.e_score == Decimal("0.00")
    assert result.total == Decimal("0.00")


def test_compute_routine_score_penalty_subtracts_even_with_no_marks():
    result = compute_routine_score(_routine([], penalty="0.30"))

    assert result.penalty == Decimal("0.30")
    assert result.total == Decimal("-0.30")


def test_compute_routine_score_missing_panel_scores_zero():
    routine = _routine(
        [
            _mark(Panel.artistry, "9.5"),
            _mark(Panel.artistry, "9.0"),
            _mark(Panel.artistry, "9.25"),
        ]
    )

    result = compute_routine_score(routine)

    assert result.a_score == Decimal("9.25")
    assert result.d_score == Decimal("0.00")
    assert result.e_score == Decimal("0.00")
    assert result.total == Decimal("9.25")


def test_compute_routine_score_rounds_to_two_decimal_places():
    # plain mean of these three is 9.0333... (repeating) -- this only comes out to
    # "9.03" if compute_routine_score actually rounds, rather than passing through
    # trimmed_mean's full-precision Decimal untouched.
    routine = _routine(
        [
            _mark(Panel.artistry, "9.0"),
            _mark(Panel.artistry, "9.0"),
            _mark(Panel.artistry, "9.1"),
        ]
    )

    result = compute_routine_score(routine)

    assert str(result.a_score) == "9.03"


def test_compute_routine_score_composes_full_panel_and_penalty():
    routine = _routine(
        [
            _mark(Panel.difficulty_body, "3.30"),
            _mark(Panel.difficulty_apparatus, "2.00"),
            _mark(Panel.artistry, "9.5"),
            _mark(Panel.artistry, "9.0"),
            _mark(Panel.artistry, "9.25"),
            _mark(Panel.execution, "8.5"),
            _mark(Panel.execution, "8.7"),
            _mark(Panel.execution, "8.6"),
            _mark(Panel.execution, "9.9"),
        ],
        penalty="0.30",
    )

    result = compute_routine_score(routine)

    assert isinstance(result, RoutineScoreResult)
    assert result.d_score == Decimal("5.30")  # difficulty_body (3.30) + difficulty_apparatus (2.00)
    assert result.a_score == Decimal("9.25")
    assert result.e_score == Decimal("8.65")  # trimmed mean of [8.5,8.6,8.7,9.9] -> [8.6,8.7]
    assert result.penalty == Decimal("0.30")
    assert result.total == Decimal("22.90")


def test_compute_routine_score_d_score_sums_body_and_apparatus_subgroups():
    # Per FIG's Code of Points, D is the SUM of two independently-judged subgroups,
    # not a single trimmed mean over a pooled set of "difficulty" marks. Using >=4
    # marks in each subgroup (so trimmed_mean actually trims) with values that would
    # produce a very different (wrong) result if the two subgroups were pooled together
    # instead of reduced separately and summed.
    routine = _routine(
        [
            _mark(Panel.difficulty_body, "5.00"),
            _mark(Panel.difficulty_body, "5.20"),
            _mark(Panel.difficulty_body, "5.10"),
            _mark(Panel.difficulty_body, "9.90"),
            _mark(Panel.difficulty_apparatus, "3.00"),
            _mark(Panel.difficulty_apparatus, "3.30"),
            _mark(Panel.difficulty_apparatus, "3.10"),
            _mark(Panel.difficulty_apparatus, "0.00"),
        ]
    )

    result = compute_routine_score(routine)

    # difficulty_body: sorted [5.00,5.10,5.20,9.90] -> trim -> [5.10,5.20] -> mean 5.15
    # difficulty_apparatus: sorted [0.00,3.00,3.10,3.30] -> trim -> [3.00,3.10] -> mean 3.05
    assert result.d_score == Decimal("8.20")


def test_compute_routine_score_d_score_uses_only_one_subgroup_when_other_is_empty():
    routine = _routine([_mark(Panel.difficulty_body, "6.40")])

    result = compute_routine_score(routine)

    assert result.d_score == Decimal("6.40")


def test_compute_routine_score_d_score_is_not_capped_at_10():
    routine = _routine(
        [
            _mark(Panel.difficulty_body, "9.80"),
            _mark(Panel.difficulty_apparatus, "8.40"),
        ]
    )

    result = compute_routine_score(routine)

    assert result.d_score == Decimal("18.20")


@pytest.mark.parametrize("level", [Level.level_1, Level.level_7])
@pytest.mark.parametrize("panel", list(Panel))
def test_is_panel_valid_for_level_e_only_levels(level, panel):
    assert is_panel_valid_for_level(level, panel) == (panel == Panel.execution)


@pytest.mark.parametrize(
    "level", [Level.level_8, Level.high_performance_1, Level.senior, Level.olympic]
)
@pytest.mark.parametrize("panel", list(Panel))
def test_is_panel_valid_for_level_non_gated_levels(level, panel):
    assert is_panel_valid_for_level(level, panel) is True


def _entry(routines):
    return SimpleNamespace(routines=routines)


def test_rank_apparatus_orders_by_total_descending():
    low = _routine([_mark(Panel.execution, "6.00")])
    mid = _routine([_mark(Panel.execution, "8.00")])
    high = _routine([_mark(Panel.execution, "9.50")])

    standings = rank_apparatus([low, high, mid])

    assert [s.rank for s in standings] == [1, 2, 3]
    assert [s.routine for s in standings] == [high, mid, low]
    assert all(isinstance(s, ApparatusStanding) for s in standings)


def test_rank_apparatus_execution_tiebreak_on_equal_totals():
    # Equal totals (20.00) but different Execution -- higher Execution ranks first.
    lower_execution = _routine(
        [
            _mark(Panel.difficulty_body, "10.00"),
            _mark(Panel.artistry, "5.00"),
            _mark(Panel.execution, "5.00"),
        ]
    )
    higher_execution = _routine(
        [
            _mark(Panel.difficulty_body, "8.00"),
            _mark(Panel.artistry, "5.00"),
            _mark(Panel.execution, "7.00"),
        ]
    )

    standings = rank_apparatus([lower_execution, higher_execution])

    assert [s.routine for s in standings] == [higher_execution, lower_execution]
    assert [s.rank for s in standings] == [1, 2]


def test_rank_apparatus_shares_rank_on_full_tie():
    tied_a = _routine([_mark(Panel.execution, "9.00")])
    tied_b = _routine([_mark(Panel.execution, "9.00")])
    lowest = _routine([_mark(Panel.execution, "7.00")])

    standings = rank_apparatus([tied_a, tied_b, lowest])

    ranks_by_routine = {id(s.routine): s.rank for s in standings}
    assert ranks_by_routine[id(tied_a)] == 1
    assert ranks_by_routine[id(tied_b)] == 1
    assert ranks_by_routine[id(lowest)] == 3  # rank 2 is skipped


def test_rank_apparatus_empty_input_returns_empty_list():
    assert rank_apparatus([]) == []


def test_rank_all_around_sums_totals_across_routines_and_ranks():
    entry_a = _entry([_routine([_mark(Panel.execution, "9.00")])])
    entry_b = _entry(
        [
            _routine([_mark(Panel.execution, "9.00")]),
            _routine([_mark(Panel.execution, "8.00")]),
        ]
    )

    standings = rank_all_around([entry_a, entry_b])

    assert all(isinstance(s, AllAroundStanding) for s in standings)
    by_entry = {id(s.entry): s for s in standings}
    assert by_entry[id(entry_b)].total == Decimal("17.00")
    assert by_entry[id(entry_a)].total == Decimal("9.00")
    assert by_entry[id(entry_b)].rank == 1
    assert by_entry[id(entry_a)].rank == 2


def test_rank_all_around_routines_counted_reflects_partial_sets():
    complete = _entry(
        [
            _routine([_mark(Panel.execution, "9.00")]),
            _routine([_mark(Panel.execution, "9.00")]),
        ]
    )
    partial = _entry([_routine([_mark(Panel.execution, "9.50")])])

    standings = rank_all_around([complete, partial])

    by_entry = {id(s.entry): s for s in standings}
    assert by_entry[id(complete)].routines_counted == 2
    assert by_entry[id(partial)].routines_counted == 1
    # A partial set is ranked on its own (smaller) total, not dropped.
    assert by_entry[id(partial)].total == Decimal("9.50")
    assert by_entry[id(complete)].total == Decimal("18.00")
    assert by_entry[id(complete)].rank == 1
    assert by_entry[id(partial)].rank == 2


def test_rank_all_around_execution_tiebreak_on_equal_totals():
    lower_execution = _entry(
        [
            _routine(
                [
                    _mark(Panel.difficulty_body, "10.00"),
                    _mark(Panel.artistry, "5.00"),
                    _mark(Panel.execution, "5.00"),
                ]
            )
        ]
    )
    higher_execution = _entry(
        [
            _routine(
                [
                    _mark(Panel.difficulty_body, "8.00"),
                    _mark(Panel.artistry, "5.00"),
                    _mark(Panel.execution, "7.00"),
                ]
            )
        ]
    )

    standings = rank_all_around([lower_execution, higher_execution])

    assert [s.entry for s in standings] == [higher_execution, lower_execution]
    assert [s.rank for s in standings] == [1, 2]


def test_rank_all_around_shares_rank_on_full_tie():
    tied_a = _entry([_routine([_mark(Panel.execution, "9.00")])])
    tied_b = _entry([_routine([_mark(Panel.execution, "9.00")])])
    lowest = _entry([_routine([_mark(Panel.execution, "7.00")])])

    standings = rank_all_around([tied_a, tied_b, lowest])

    ranks_by_entry = {id(s.entry): s.rank for s in standings}
    assert ranks_by_entry[id(tied_a)] == 1
    assert ranks_by_entry[id(tied_b)] == 1
    assert ranks_by_entry[id(lowest)] == 3  # rank 2 is skipped


def test_rank_all_around_empty_input_returns_empty_list():
    assert rank_all_around([]) == []
