"""
Routine router — CRUD for /routines.

Design notes:
- A routine belongs to a meet entry (entry_id). POST pre-checks that the
  entry exists (404 if missing) before constructing the row — SQLite's FK
  enforcement isn't guaranteed on in the real app (only test fixtures turn
  it on), so we can't rely on IntegrityError to catch a bad entry_id.
- apparatus + entry_id form a UniqueConstraint (one row per apparatus per
  entry), so IntegrityError -> 409 covers "this apparatus is already
  registered for this entry."
- GET filters: ?entry_id= lets you list all routines for one entry.
- PATCH: entry_id/apparatus are not updatable (locked in at creation, per
  RoutineUpdate) — only order_of_performance and penalty change, so no FK
  pre-check needed. Direct penalty edits are rejected (409) once the
  routine has any PenaltyRecords (app/routers/penalty_record.py) — once
  itemization has started for a routine, penalty must only change via
  itemized records, so the aggregate can't be hand-edited out of sync with
  their sum.
- DELETE: nothing references Routine as a parent, so no IntegrityError can
  occur — no try/except needed, matching meet_entry.py's delete.
- GET /{routine_id}/score computes the routine's D/A/E/total live via
  compute_routine_score (app/scoring.py), same "resolve live, don't
  snapshot" philosophy as Routine.music_url. It's a separate endpoint
  rather than fields embedded in RoutineRead: computing a trimmed mean over
  every routine's judge_scores on every plain GET/list call would be
  wasted cost for callers who only need schedule metadata.
- POST/PATCH/DELETE all reject (409) once the routine's meet is completed
  (app/routers/_guards.py) -- a completed meet is the historical record of
  who competed, so its routines can't be created, edited, or deleted after
  the fact. Same guard is shared by judge_score.py and penalty_record.py.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import MeetEntry, Routine
from app.routers._guards import ensure_meet_not_completed
from app.schemas.routine import RoutineCreate, RoutineRead, RoutineScoreRead, RoutineUpdate
from app.scoring import compute_routine_score

router = APIRouter(prefix="/routines", tags=["Routines"])


##-- Post --##
@router.post("/", response_model=RoutineRead, status_code=status.HTTP_201_CREATED)
def create_routine(payload: RoutineCreate, db: Annotated[Session, Depends(get_db)]):
    entry = db.get(MeetEntry, payload.entry_id)

    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meet entry with id {payload.entry_id} not found",
        )

    ensure_meet_not_completed(entry.meet)

    routine = Routine(**payload.model_dump())
    db.add(routine)

    try:
        db.flush()
        db.commit()
        db.refresh(routine)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Integrity error while creating routine.",
        ) from e

    return routine


##-- Get --##
@router.get("/", response_model=list[RoutineRead])
def list_routines(
    db: Annotated[Session, Depends(get_db)],
    entry_id: Annotated[int | None, Query(description="Filter by entry_id")] = None,
) -> list[Routine]:
    query = db.query(Routine)
    if entry_id is not None:
        query = query.filter(Routine.entry_id == entry_id)

    return query.all()


@router.get("/{routine_id}", response_model=RoutineRead)
def get_routine(routine_id: int, db: Annotated[Session, Depends(get_db)]) -> Routine:
    routine = db.get(Routine, routine_id)
    if routine is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Routine with id {routine_id} not found"
        )
    return routine


@router.get("/{routine_id}/score", response_model=RoutineScoreRead)
def get_routine_score(routine_id: int, db: Annotated[Session, Depends(get_db)]) -> RoutineScoreRead:
    routine = db.get(Routine, routine_id)
    if routine is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Routine with id {routine_id} not found"
        )

    result = compute_routine_score(routine)
    return RoutineScoreRead(
        routine_id=routine.id,
        d_score=result.d_score,
        a_score=result.a_score,
        e_score=result.e_score,
        final_score=result.final_score,
        penalty=result.penalty,
        total=result.total,
    )


##-- Patch --##
@router.patch("/{routine_id}", response_model=RoutineRead)
def update_routine(
    routine_id: int, payload: RoutineUpdate, db: Annotated[Session, Depends(get_db)]
) -> Routine:
    routine = db.get(Routine, routine_id)
    if routine is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Routine with id {routine_id} not found"
        )

    ensure_meet_not_completed(routine.entry.meet)

    updates = payload.model_dump(exclude_unset=True)
    if "penalty" in updates and routine.penalty_records:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Routine {routine_id} has itemized penalty records -- edit those "
                "instead of setting penalty directly."
            ),
        )

    for field, value in updates.items():
        setattr(routine, field, value)

    try:
        db.flush()
        db.commit()
        db.refresh(routine)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Integrity error while updating routine.",
        ) from e

    return routine


##-- Delete --##
@router.delete("/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_routine(routine_id: int, db: Annotated[Session, Depends(get_db)]) -> None:
    routine = db.get(Routine, routine_id)
    if routine is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Routine with id {routine_id} not found"
        )

    ensure_meet_not_completed(routine.entry.meet)

    db.delete(routine)
    db.commit()
