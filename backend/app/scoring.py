from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.models import Level, Panel

TRIM_THRESHOLD = 4  # Minimum number of scores required to calculate trimmed mean

# Levels 1-7 are scored on Execution only -- no Difficulty (D) or Artistry (A) panels
# are judged at these levels. level_8 and above (level_8-10, high_performance_1-4,
# pre_junior, junior, senior, olympic) receive the full D+A+E panel.
E_ONLY_LEVELS = frozenset(
    {
        Level.level_1,
        Level.level_2,
        Level.level_3,
        Level.level_4,
        Level.level_5,
        Level.level_6,
        Level.level_7,
    }
)


def is_panel_valid_for_level(level: Level, panel: Panel) -> bool:
    """Whether a judge score on `panel` is valid for a routine at `level`."""
    if level in E_ONLY_LEVELS:
        return panel == Panel.execution
    return True


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

    Note: per FIG's Code of Points, D is the *sum* of two independently-judged
    subgroups (difficulty_body + difficulty_apparatus), not a trimmed mean of a single
    pool like artistry/execution -- each subgroup is reduced with the same trimmed_mean
    as A/E, then the two results are added together.
    """
    by_panel: dict[Panel, list[Decimal]] = {panel: [] for panel in Panel}
    for judge_score in routine.judge_scores:
        by_panel[judge_score.panel].append(judge_score.value)

    def rounded(values: list[Decimal]) -> Decimal:
        return trimmed_mean(values).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    db_score = rounded(by_panel[Panel.difficulty_body])
    da_score = rounded(by_panel[Panel.difficulty_apparatus])
    d_score = db_score + da_score
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


@dataclass(frozen=True)
class ApparatusStanding:
    rank: int
    routine: object
    score: RoutineScoreResult


@dataclass(frozen=True)
class AllAroundStanding:
    rank: int
    entry: object
    total: Decimal
    e_total: Decimal
    routines_counted: int


def _assign_ranks(rows: list, key_fn) -> list[int]:
    """
    Competition ranking (1,2,2,4): `rows` must already be sorted best-first. Rows with an
    equal `key_fn` value share a rank; the next distinct value's rank skips ahead to its
    1-based position in `rows`, rather than incrementing by 1.

    Returns a list of ranks, one per row in `rows`, in the same order.
    """
    ranks: list[int] = []
    for i, row in enumerate(rows):
        if i > 0 and key_fn(row) == key_fn(rows[i - 1]):
            ranks.append(ranks[-1])
        else:
            ranks.append(i + 1)
    return ranks


def rank_apparatus(routines) -> list[ApparatusStanding]:
    """
    Rank routines within a single apparatus category (caller filters to one
    (meet, level, age_group, apparatus) slice first).

    Per FIG Technical Regulations, ties are broken by total score first, then by highest
    total Execution; a routine still tied on both shares its rank with the next
    (competition ranking, see _assign_ranks).
    """
    scored = [(routine, compute_routine_score(routine)) for routine in routines]
    scored.sort(key=lambda pair: (pair[1].total, pair[1].e_score), reverse=True)

    ranks = _assign_ranks(scored, key_fn=lambda pair: (pair[1].total, pair[1].e_score))
    return [
        ApparatusStanding(rank=rank, routine=routine, score=score)
        for rank, (routine, score) in zip(ranks, scored, strict=True)
    ]


def rank_all_around(entries) -> list[AllAroundStanding]:
    """
    Rank meet entries by the sum of their routines' totals (the all-around), within a
    single (meet, level, age_group) slice (caller filters first).

    A competitor with an incomplete apparatus set (e.g. injured mid-meet) is still ranked
    on their partial sum, not excluded -- `routines_counted` lets the caller surface that
    the total is partial, matching how compute_routine_score returns 0 for missing panels
    rather than erroring. Same tie-break as rank_apparatus: total, then summed Execution,
    then shared rank.
    """
    summed = []
    for entry in entries:
        results = [compute_routine_score(routine) for routine in entry.routines]
        total = sum((result.total for result in results), Decimal("0"))
        e_total = sum((result.e_score for result in results), Decimal("0"))
        summed.append((entry, total, e_total, len(results)))

    summed.sort(key=lambda row: (row[1], row[2]), reverse=True)

    ranks = _assign_ranks(summed, key_fn=lambda row: (row[1], row[2]))
    return [
        AllAroundStanding(
            rank=rank, entry=entry, total=total, e_total=e_total, routines_counted=count
        )
        for rank, (entry, total, e_total, count) in zip(ranks, summed, strict=True)
    ]
