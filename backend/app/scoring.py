"""
FIG Code of Points scoring math: turning raw JudgeScore marks into a routine's D/A/E
panel scores and total, and ranking routines/entries from those totals. Used by
app/routers/results.py (live, never snapshotted -- see that router's module
docstring) and by app/models.py's Routine.penalty machinery indirectly via the
routers that call into here.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Literal

from app.models import Level, MeetEntry, Panel, Routine

Medal = Literal["gold", "silver", "bronze"]

TRIM_THRESHOLD = 4  # Minimum number of scores required to calculate trimmed mean


class MedalMode(StrEnum):
    """How a band decides who gets a medal (spec: "Two medal systems")."""

    cutoff = "cutoff"  # levels 1-3: Meet.medal_gold_min/medal_silver_min, on the all-around
    placement = "placement"  # levels 4+: the first three distinct RANKS


@dataclass(frozen=True)
class ScoringProfile:
    """
    Everything that varies between the three FIG scoring bands, in one place.

    This rule is needed in at least five places (backend panel validity, backend math,
    the frontend math mirror, the judge-slot panel UI, and the score form's box
    layout). Specifying it once and deriving downward is deliberate: the previous
    two-band rule was implemented independently in several of those places and drifted.

    `judges_per_panel` is the expected panel size, used by the UI to lay out score
    boxes and to decide which judge slots are required. It is not enforced at the API:
    a routine with a missing mark is incomplete, not invalid.
    """

    band: str
    panels: frozenset[Panel]
    judges_per_panel: Mapping[Panel, int]
    medal_mode: MedalMode
    tie_break_on_execution: bool


# Levels 1-3: the judges compute D+E on paper and hand the scorer one finished mark out
# of 13. From the scorer's point of view there is exactly ONE judge, so nothing is
# averaged -- the entered mark IS the routine's total.
BAND_1_3 = ScoringProfile(
    band="1-3",
    panels=frozenset({Panel.final}),
    judges_per_panel={Panel.final: 1},
    medal_mode=MedalMode.cutoff,
    tie_break_on_execution=False,
)

# Levels 4-7: two judges both score Difficulty of Body (there is no DA at this band)
# and two score Execution. D is out of 3 (13 - 10) but is deliberately NOT tracked or
# constrained -- a judge's D mark cannot exceed 3 in practice.
BAND_4_7 = ScoringProfile(
    band="4-7",
    panels=frozenset({Panel.difficulty_body, Panel.execution}),
    judges_per_panel={Panel.difficulty_body: 2, Panel.execution: 2},
    medal_mode=MedalMode.placement,
    tie_break_on_execution=False,
)

# Levels 8+: the full FIG panel. Note the deliberate asymmetry with 4-7 -- one DB judge
# and one DA judge here, versus two DB judges there (confirmed 2026-07-20).
BAND_8_PLUS = ScoringProfile(
    band="8+",
    panels=frozenset(
        {Panel.difficulty_body, Panel.difficulty_apparatus, Panel.artistry, Panel.execution}
    ),
    judges_per_panel={
        Panel.difficulty_body: 1,
        Panel.difficulty_apparatus: 1,
        Panel.artistry: 2,
        Panel.execution: 4,
    },
    medal_mode=MedalMode.placement,
    tie_break_on_execution=True,
)

_BAND_1_3_LEVELS = (Level.level_1, Level.level_2, Level.level_3)
_BAND_4_7_LEVELS = (Level.level_4, Level.level_5, Level.level_6, Level.level_7)
_BAND_8_PLUS_LEVELS = (
    Level.level_8,
    Level.level_9,
    Level.level_10,
    Level.high_performance_1,
    Level.high_performance_2,
    Level.high_performance_3,
    Level.high_performance_4,
    Level.pre_junior,
    Level.junior,
    Level.senior,
    Level.olympic,
)

# Every band is listed explicitly rather than one being the complement of the others.
# A complement silently absorbs any Level added later, which is exactly the "new level
# quietly acquires the full FIG panel" failure this map exists to prevent -- and it
# makes the coverage test below unfalsifiable. With three explicit tuples, an unbanded
# level is simply absent: profile_for_level raises KeyError and the test fails.
_PROFILE_BY_LEVEL: dict[Level, ScoringProfile] = {
    **dict.fromkeys(_BAND_1_3_LEVELS, BAND_1_3),
    **dict.fromkeys(_BAND_4_7_LEVELS, BAND_4_7),
    **dict.fromkeys(_BAND_8_PLUS_LEVELS, BAND_8_PLUS),
}


def profile_for_level(level: Level) -> ScoringProfile:
    """The scoring profile governing `level`. See ScoringProfile."""
    return _PROFILE_BY_LEVEL[level]


def is_panel_valid_for_level(level: Level, panel: Panel) -> bool:
    """Whether a judge score on `panel` is valid for a routine at `level`."""
    return panel in profile_for_level(level).panels


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


def medal_for_total(
    total: Decimal, gold_min: Decimal | None, silver_min: Decimal | None
) -> Medal | None:
    """
    Standard-based medal tier for a single total, independent of how it ranks against
    the rest of the field -- for smaller meets that award medals by a configured score
    threshold rather than 1st/2nd/3rd place. `gold_min`/`silver_min` come from the
    meet (see Meet.medal_gold_min/medal_silver_min); both null means the meet isn't
    using cutoffs, so there's no medal to report.

    Every competitor gets a tier once cutoffs are configured -- bronze has no floor,
    it's simply "below silver_min", not a fourth non-medal bucket.
    """
    if gold_min is None or silver_min is None:
        return None
    if total >= gold_min:
        return "gold"
    if total >= silver_min:
        return "silver"
    return "bronze"


@dataclass(frozen=True)
class ApparatusStanding:
    rank: int
    routine: Routine
    score: RoutineScoreResult


@dataclass(frozen=True)
class AllAroundStanding:
    rank: int
    entry: MeetEntry
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
