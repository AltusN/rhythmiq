from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models import Panel
from app.scoring import RoutineScoreResult, compute_routine_score, trimmed_mean


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
            _mark(Panel.difficulty, "5.30"),
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
    assert result.d_score == Decimal("5.30")
    assert result.a_score == Decimal("9.25")
    assert result.e_score == Decimal("8.65")  # trimmed mean of [8.5,8.6,8.7,9.9] -> [8.6,8.7]
    assert result.penalty == Decimal("0.30")
    assert result.total == Decimal("22.90")
