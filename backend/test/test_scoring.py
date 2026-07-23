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
    _PROFILE_BY_LEVEL,
    BAND_1_3,
    BAND_4_7,
    BAND_8_PLUS,
    AllAroundStanding,
    ApparatusStanding,
    MedalMode,
    RoutineScoreResult,
    assign_placement_medals,
    compute_routine_score,
    is_panel_valid_for_level,
    medal_for_total,
    rank_all_around,
    rank_apparatus,
    trimmed_mean,
)


@pytest.mark.parametrize(
    "total, gold_min, silver_min, expected",
    [
        (Decimal("25.00"), Decimal("24.00"), Decimal("20.00"), "gold"),
        (Decimal("24.00"), Decimal("24.00"), Decimal("20.00"), "gold"),  # exactly at gold_min
        (Decimal("22.00"), Decimal("24.00"), Decimal("20.00"), "silver"),
        (Decimal("20.00"), Decimal("24.00"), Decimal("20.00"), "silver"),  # exactly at silver_min
        (Decimal("19.99"), Decimal("24.00"), Decimal("20.00"), "bronze"),
        (Decimal("0.00"), Decimal("24.00"), Decimal("20.00"), "bronze"),  # no floor under bronze
        (Decimal("25.00"), None, None, None),  # meet isn't using cutoffs
    ],
)
def test_medal_for_total(total, gold_min, silver_min, expected):
    assert medal_for_total(total, gold_min, silver_min) == expected


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


def _routine(marks, penalty="0", level=Level.senior):
    # Defaults to a level-8+ band so the pre-existing full-FIG worked examples below
    # keep exercising the (DB + DA) + A + E path unchanged.
    return SimpleNamespace(
        judge_scores=marks,
        penalty=Decimal(penalty),
        entry=SimpleNamespace(level=level),
    )


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


@pytest.mark.parametrize(
    "level, valid_panels",
    [
        (Level.level_1, {Panel.final}),
        (Level.level_3, {Panel.final}),
        (Level.level_4, {Panel.difficulty_body, Panel.execution}),
        (Level.level_7, {Panel.difficulty_body, Panel.execution}),
        (
            Level.level_8,
            {
                Panel.difficulty_body,
                Panel.difficulty_apparatus,
                Panel.artistry,
                Panel.execution,
            },
        ),
        (
            Level.senior,
            {
                Panel.difficulty_body,
                Panel.difficulty_apparatus,
                Panel.artistry,
                Panel.execution,
            },
        ),
    ],
)
@pytest.mark.parametrize("panel", list(Panel))
def test_is_panel_valid_for_level(level, valid_panels, panel):
    assert is_panel_valid_for_level(level, panel) == (panel in valid_panels)


def test_every_level_is_explicitly_banded():
    # Set equality, not per-level lookup: no band is built as the complement of the
    # others, so a Level added to the enum without a band assignment is simply missing
    # here and this fails -- which is the whole point of the map being explicit.
    assert set(_PROFILE_BY_LEVEL) == set(Level)


def test_band_profiles_match_the_spec():
    assert BAND_1_3.medal_mode is MedalMode.cutoff
    assert BAND_1_3.tie_break_on_execution is False
    assert BAND_1_3.judges_per_panel == {Panel.final: 4}

    assert BAND_4_7.medal_mode is MedalMode.placement
    assert BAND_4_7.tie_break_on_execution is False
    # Deliberate asymmetry (spec, confirmed 2026-07-20): TWO DB judges here, but one DB
    # and one DA at 8+. Do not "fix" this into consistency.
    assert BAND_4_7.judges_per_panel == {Panel.difficulty_body: 2, Panel.execution: 2}

    assert BAND_8_PLUS.medal_mode is MedalMode.placement
    assert BAND_8_PLUS.tie_break_on_execution is True
    assert BAND_8_PLUS.judges_per_panel == {
        Panel.difficulty_body: 1,
        Panel.difficulty_apparatus: 1,
        Panel.artistry: 2,
        Panel.execution: 4,
    }


def _entry(routines, level=Level.senior):
    return SimpleNamespace(routines=routines, level=level)


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


def test_compute_routine_score_level_1_3_records_the_final_mark():
    # The application is not calculating a score at this band; it is recording one.
    routine = _routine([_mark(Panel.final, "11.75")], level=Level.level_2)

    result = compute_routine_score(routine)

    assert result.final_score == Decimal("11.75")
    assert result.total == Decimal("11.75")
    assert result.d_score == Decimal("0")
    assert result.a_score == Decimal("0")
    assert result.e_score == Decimal("0")


def test_compute_routine_score_level_1_3_subtracts_penalty():
    routine = _routine([_mark(Panel.final, "12.00")], penalty="0.30", level=Level.level_3)

    result = compute_routine_score(routine)

    assert result.total == Decimal("11.70")


def test_compute_routine_score_level_1_3_ignores_marks_on_other_panels():
    # Stale/illegal marks (direct ORM writes bypass the API's panel gate) must not leak
    # into a band-1-3 total.
    routine = _routine(
        [_mark(Panel.final, "10.00"), _mark(Panel.execution, "9.00")],
        level=Level.level_1,
    )

    result = compute_routine_score(routine)

    assert result.e_score == Decimal("0")
    assert result.total == Decimal("10.00")


def test_band_1_3_trims_four_final_marks_to_the_middle_two():
    # [10, 11, 12, 13] -> drop 10 and 13 -> mean(11, 12) = 11.50
    routine = _routine(
        [
            _mark(Panel.final, "10"),
            _mark(Panel.final, "11"),
            _mark(Panel.final, "12"),
            _mark(Panel.final, "13"),
        ],
        level=Level.level_1,
    )

    result = compute_routine_score(routine)

    assert result.final_score == Decimal("11.50")
    assert result.total == Decimal("11.50")


def test_band_1_3_plain_averages_three_final_marks():
    # Three marks is a complete (minimum viable) panel: plain average, no trim.
    # [10, 11, 12] -> mean = 11.00
    routine = _routine(
        [_mark(Panel.final, "10"), _mark(Panel.final, "11"), _mark(Panel.final, "12")],
        level=Level.level_1,
    )

    assert compute_routine_score(routine).final_score == Decimal("11.00")


def test_band_1_3_single_final_mark_is_that_mark():
    # Backwards compatible: one mark still yields that mark.
    routine = _routine([_mark(Panel.final, "12.5")], level=Level.level_1)

    assert compute_routine_score(routine).final_score == Decimal("12.50")


def test_compute_routine_score_level_4_7_averages_the_two_db_marks():
    # No DA exists at this band, so trimmed_mean([]) returns 0 and the shipped additive
    # formula (DB + DA) already yields avg(DB1, DB2). Adding zero is a no-op.
    routine = _routine(
        [
            _mark(Panel.difficulty_body, "2.40"),
            _mark(Panel.difficulty_body, "2.60"),
            _mark(Panel.execution, "8.50"),
            _mark(Panel.execution, "8.70"),
        ],
        level=Level.level_5,
    )

    result = compute_routine_score(routine)

    assert result.d_score == Decimal("2.50")
    assert result.e_score == Decimal("8.60")
    assert result.final_score == Decimal("0")
    assert result.total == Decimal("11.10")


def test_compute_routine_score_level_4_7_ignores_marks_on_out_of_band_panels():
    # Same protection band 1-3 gets: the API's panel gate is HTTP-only, so a stale
    # artistry or difficulty_apparatus mark can reach a level 4-7 routine via a direct
    # ORM write. Scoring it would inflate the total.
    routine = _routine(
        [
            _mark(Panel.difficulty_body, "2.40"),
            _mark(Panel.difficulty_body, "2.60"),
            _mark(Panel.execution, "8.50"),
            _mark(Panel.execution, "8.70"),
            _mark(Panel.difficulty_apparatus, "3.00"),
            _mark(Panel.artistry, "9.00"),
        ],
        level=Level.level_5,
    )

    result = compute_routine_score(routine)

    assert result.d_score == Decimal("2.50")
    assert result.a_score == Decimal("0")
    assert result.total == Decimal("11.10")


def test_compute_routine_score_8_plus_is_unchanged_and_has_zero_final():
    routine = _routine(
        [
            _mark(Panel.difficulty_body, "5.00"),
            _mark(Panel.difficulty_apparatus, "3.00"),
            _mark(Panel.artistry, "8.00"),
            _mark(Panel.execution, "9.00"),
        ]
    )

    result = compute_routine_score(routine)

    assert result.final_score == Decimal("0")
    assert result.total == Decimal("25.00")


def test_compute_routine_score_8_plus_ignores_marks_on_final_panel():
    # Companion to the band 1-3 and 4-7 out-of-band guards: Panel.final is illegal at
    # level 8+ (there is no pre-aggregated judge at this band), so a stray final mark
    # left by a direct ORM write must not be added into the total.
    routine = _routine(
        [
            _mark(Panel.difficulty_body, "5.00"),
            _mark(Panel.difficulty_apparatus, "3.00"),
            _mark(Panel.artistry, "8.00"),
            _mark(Panel.execution, "9.00"),
            _mark(Panel.final, "11.00"),
        ]
    )

    result = compute_routine_score(routine)

    # d_score = difficulty_body (5.00) + difficulty_apparatus (3.00) = 8.00
    # a_score = trimmed_mean([8.00]) = 8.00 (single mark, no trimming below TRIM_THRESHOLD)
    # e_score = trimmed_mean([9.00]) = 9.00
    # total = 8.00 + 8.00 + 9.00 - 0 penalty = 25.00 -- identical to the total without the
    # stray final mark, proving the illegal 11.00 mark contributed nothing.
    assert result.final_score == Decimal("0.00")
    assert result.total == Decimal("25.00")


def test_rank_apparatus_breaks_ties_on_execution_at_level_8_plus():
    lower_e = _routine([_mark(Panel.difficulty_body, "6.00"), _mark(Panel.execution, "8.00")])
    higher_e = _routine([_mark(Panel.difficulty_body, "5.00"), _mark(Panel.execution, "9.00")])

    standings = rank_apparatus([lower_e, higher_e])

    assert [standing.routine for standing in standings] == [higher_e, lower_e]
    assert [standing.rank for standing in standings] == [1, 2]


def test_rank_apparatus_does_not_break_ties_on_execution_at_levels_4_7():
    # Spec: no tie-breaks below level 8. Equal totals share a rank even when their
    # Execution differs.
    lower_e = _routine(
        [_mark(Panel.difficulty_body, "3.00"), _mark(Panel.execution, "8.00")],
        level=Level.level_5,
    )
    higher_e = _routine(
        [_mark(Panel.difficulty_body, "2.00"), _mark(Panel.execution, "9.00")],
        level=Level.level_5,
    )

    standings = rank_apparatus([lower_e, higher_e])

    assert [standing.rank for standing in standings] == [1, 1]


def test_rank_all_around_does_not_break_ties_on_execution_at_levels_1_3():
    a = _entry([_routine([_mark(Panel.final, "12.00")], level=Level.level_1)], level=Level.level_1)
    b = _entry([_routine([_mark(Panel.final, "12.00")], level=Level.level_1)], level=Level.level_1)

    standings = rank_all_around([a, b])

    assert [standing.rank for standing in standings] == [1, 1]


@pytest.mark.parametrize(
    "ranks, expected",
    [
        ([1, 2, 3, 4], ["gold", "silver", "bronze", None]),
        # Two tied at top: distinct ranks are 1, 3, 4 -> two golds, then silver, bronze.
        ([1, 1, 3, 4], ["gold", "gold", "silver", "bronze"]),
        # One winner, two tied second: distinct ranks 1, 2, 4 -> the 4th-place gymnast
        # still takes bronze. A `rank <= 3` implementation would deny it.
        ([1, 2, 2, 4], ["gold", "silver", "silver", "bronze"]),
        ([1, 1, 1, 4], ["gold", "gold", "gold", "silver"]),
        ([1, 2], ["gold", "silver"]),
        ([], []),
    ],
)
def test_assign_placement_medals(ranks, expected):
    assert assign_placement_medals(ranks) == expected
