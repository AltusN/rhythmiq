"""
Results router — read-only reporting for /meets/{meet_id}/standings and
/meets/{meet_id}/all-around.

Design notes:
- Deliberately not CRUD-shaped like every other router: these are computed views over
  existing data, not a resource with its own table, so there's no POST/PATCH/DELETE.
- Both endpoints compute live off compute_routine_score / rank_apparatus / rank_all_around
  (app/scoring.py) on every call rather than snapshotting a result -- same "resolve live,
  don't snapshot" philosophy as Routine.music_url and GET /routines/{id}/score.
- `provisional` is true unless meet.status == MeetStatus.completed, so callers can tell a
  mid-meet standings snapshot from the final one.
- /standings requires `apparatus` (a per-apparatus ranking is undefined without one);
  /all-around has no apparatus filter since it deliberately spans all of them. Both accept
  optional `level`/`age_group` filters, applied against MeetEntry, matching meet_entry.py's
  filter style.
- A missing meet is the only 404 case; an empty category returns 200 with `rankings: []`.
- `medal` on each row is additive to `rank`, not a replacement: it's a standard-based
  tier (gold/silver/bronze) from the meet's configured `medal_gold_min`/
  `medal_silver_min` cutoffs, answering "did this total clear a threshold" rather
  than "how did this total compare to the field". Multiple rows (or none) can share
  a medal tier. Both cutoffs null (the default) means the meet isn't using them, so
  every row's `medal` is null -- see `medal_for_total` in `app/scoring.py`.
- These endpoints iterate every routine in a meet on every call (compute_routine_score reads
  routine.judge_scores), so -- unlike the single-row CRUD endpoints elsewhere in this
  codebase -- they eager-load with selectinload to avoid an N+1 over the whole meet.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Apparatus, Meet, MeetEntry, MeetStatus, Routine
from app.schemas.results import (
    AllAroundStandingRow,
    AllAroundStandingsRead,
    ApparatusStandingRow,
    ApparatusStandingsRead,
)
from app.scoring import medal_for_total, rank_all_around, rank_apparatus

router = APIRouter(prefix="/meets", tags=["Results"])


def _competitor_name(entry: MeetEntry) -> str:
    if entry.gymnast_id is not None:
        return f"{entry.gymnast.first_name} {entry.gymnast.last_name}"
    return entry.group.name


@router.get("/{meet_id}/standings", response_model=ApparatusStandingsRead)
def get_apparatus_standings(
    meet_id: int,
    db: Annotated[Session, Depends(get_db)],
    apparatus: Annotated[Apparatus, Query(description="Apparatus to rank (required).")],
    level: Annotated[str | None, Query(description="Filter by level")] = None,
    age_group: Annotated[str | None, Query(description="Filter by age_group")] = None,
) -> ApparatusStandingsRead:
    meet = db.get(Meet, meet_id)
    if meet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Meet with id {meet_id} not found"
        )

    query = (
        db.query(Routine)
        .join(MeetEntry)
        .filter(MeetEntry.meet_id == meet_id, Routine.apparatus == apparatus)
        .options(selectinload(Routine.judge_scores))
    )
    if level is not None:
        query = query.filter(MeetEntry.level == level)
    if age_group is not None:
        query = query.filter(MeetEntry.age_group == age_group)

    standings = rank_apparatus(query.all())

    return ApparatusStandingsRead(
        meet_id=meet_id,
        provisional=meet.status != MeetStatus.completed,
        apparatus=apparatus,
        level=level,
        age_group=age_group,
        rankings=[
            ApparatusStandingRow(
                rank=standing.rank,
                entry_id=standing.routine.entry_id,
                routine_id=standing.routine.id,
                competitor_name=_competitor_name(standing.routine.entry),
                bib_number=standing.routine.entry.bib_number,
                level=standing.routine.entry.level,
                age_group=standing.routine.entry.age_group,
                apparatus=standing.routine.apparatus,
                d_score=standing.score.d_score,
                a_score=standing.score.a_score,
                e_score=standing.score.e_score,
                penalty=standing.score.penalty,
                total=standing.score.total,
                medal=medal_for_total(
                    standing.score.total, meet.medal_gold_min, meet.medal_silver_min
                ),
            )
            for standing in standings
        ],
    )


@router.get("/{meet_id}/all-around", response_model=AllAroundStandingsRead)
def get_all_around_standings(
    meet_id: int,
    db: Annotated[Session, Depends(get_db)],
    level: Annotated[str | None, Query(description="Filter by level")] = None,
    age_group: Annotated[str | None, Query(description="Filter by age_group")] = None,
) -> AllAroundStandingsRead:
    meet = db.get(Meet, meet_id)
    if meet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Meet with id {meet_id} not found"
        )

    query = (
        db.query(MeetEntry)
        .filter(MeetEntry.meet_id == meet_id)
        .options(
            selectinload(MeetEntry.routines).selectinload(Routine.judge_scores),
            selectinload(MeetEntry.gymnast),
            selectinload(MeetEntry.group),
        )
    )
    if level is not None:
        query = query.filter(MeetEntry.level == level)
    if age_group is not None:
        query = query.filter(MeetEntry.age_group == age_group)

    standings = rank_all_around(query.all())

    return AllAroundStandingsRead(
        meet_id=meet_id,
        provisional=meet.status != MeetStatus.completed,
        level=level,
        age_group=age_group,
        rankings=[
            AllAroundStandingRow(
                rank=standing.rank,
                entry_id=standing.entry.id,
                competitor_name=_competitor_name(standing.entry),
                bib_number=standing.entry.bib_number,
                level=standing.entry.level,
                age_group=standing.entry.age_group,
                total=standing.total,
                e_total=standing.e_total,
                routines_counted=standing.routines_counted,
                medal=medal_for_total(standing.total, meet.medal_gold_min, meet.medal_silver_min),
            )
            for standing in standings
        ],
    )
