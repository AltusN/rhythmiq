from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.models import Panel

TRIM_THRESHOLD = 4  # Minimum number of scores required to calculate trimmed mean


def trimmed_mean(scores: list[Decimal]) -> Decimal:
    """
    Calculate the trimmed mean of a list of scores.

    The trimmed mean is calculated by removing the highest and lowest scores
    and then averaging the remaining scores. If there are fewer than TRIM_THRESHOLD scores,
    the function returns 0.

    Args:
        scores (list[Decimal]): A list of Decimal scores.

    Returns:
        Decimal: The trimmed mean of the scores, or 0 if there are fewer than TRIM_THRESHOLD scores.
    """
    if len(scores) < TRIM_THRESHOLD:
        # return the average of the scores if there are fewer than TRIM_THRESHOLD scores
        return sum(scores) / Decimal(len(scores)) if scores else Decimal(0)

    sorted_scores = sorted(scores)
    trimmed_scores = sorted_scores[1:-1]  # Remove the lowest and highest score
    return sum(trimmed_scores) / Decimal(len(trimmed_scores))


@dataclass(frozen=True)
class RoutineScoreResult:
    d_score: Decimal
    a_score: Decimal
    e_score: Decimal
    penalty: Decimal
    total: Decimal


def compute_routine_score(routine) -> RoutineScoreResult:
    """
    Compute a routine's D/A/E scores and total from its raw JudgeScore marks.

    Args:
        routine: A Routine ORM instance. Its `judge_scores` are grouped by panel and
        reduced via `trimmed_mean`; a panel with no marks yet contributes 0.

    Returns:
        RoutineScoreResult: the per-panel scores, penalty, and total, each rounded to
        2 decimal places to match the Numeric(6, 2) DB columns.
    """
    by_panel: dict[Panel, list[Decimal]] = {panel: [] for panel in Panel}
    for judge_score in routine.judge_scores:
        by_panel[judge_score.panel].append(judge_score.value)

    def rounded(values: list[Decimal]) -> Decimal:
        return trimmed_mean(values).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    d_score = rounded(by_panel[Panel.difficulty])
    a_score = rounded(by_panel[Panel.artistry])
    e_score = rounded(by_panel[Panel.execution])
    penalty = routine.penalty
    total = (d_score + a_score + e_score - penalty).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    return RoutineScoreResult(
        d_score=d_score,
        a_score=a_score,
        e_score=e_score,
        penalty=penalty,
        total=total,
    )
