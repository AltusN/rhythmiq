"""
PenaltyRecord router — CRUD for /penalty-records.

Design notes:
- A penalty record belongs to a routine (routine_id) and names the judge who assessed
  it (judge_id). Both are pre-checked for existence on create (404 each), same pattern
  as judge_score.py.
- No uniqueness constraint: the same judge_role can legitimately recur multiple times
  on one routine (e.g. two separate boundary touches by the Line judge), unlike
  JudgeScore's uq_judge_score_routine_judge_panel.
- PATCH: routine_id/judge_id are locked as identity (delete + recreate instead, matching
  MeetEntry/RoutineProfile/JudgeScore). judge_role IS updatable here -- it's a plain
  descriptive field, not part of any constraint.
- Every POST/PATCH/DELETE re-syncs Routine.penalty to the sum of its PenaltyRecords via
  _resync_routine_penalty, so the aggregate column can never drift from the itemized
  total. This intentionally overwrites any prior manually-set Routine.penalty the first
  time a record is added for that routine -- itemization takes over, it doesn't merge
  with whatever aggregate figure was there before. See routine.py's PATCH guard, which
  rejects direct penalty edits once a routine has any PenaltyRecords, keeping the two
  entry paths from fighting each other.
"""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Judge, PenaltyJudgeRole, PenaltyRecord, Routine
from app.schemas.penalty_record import (
    PenaltyRecordCreate,
    PenaltyRecordRead,
    PenaltyRecordUpdate,
)

router = APIRouter(prefix="/penalty-records", tags=["Penalty Records"])


def _resync_routine_penalty(db: Session, routine: Routine) -> None:
    """Recompute Routine.penalty as the sum of its PenaltyRecords. Caller must flush
    any pending add/update/delete first so this SQL sum sees the change."""
    total = (
        db.query(func.sum(PenaltyRecord.amount))
        .filter(PenaltyRecord.routine_id == routine.id)
        .scalar()
    )
    routine.penalty = total or Decimal("0")


##-- Post --##
@router.post("/", response_model=PenaltyRecordRead, status_code=status.HTTP_201_CREATED)
def create_penalty_record(payload: PenaltyRecordCreate, db: Annotated[Session, Depends(get_db)]):
    """
    Create a new penalty record.
    """
    routine = db.get(Routine, payload.routine_id)
    if routine is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Routine with id {payload.routine_id} not found",
        )
    judge = db.get(Judge, payload.judge_id)
    if judge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Judge with id {payload.judge_id} not found",
        )

    penalty_record = PenaltyRecord(**payload.model_dump())
    db.add(penalty_record)

    try:
        db.flush()
        _resync_routine_penalty(db, routine)
        db.commit()
        db.refresh(penalty_record)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Integrity error while creating penalty record.",
        ) from e

    return penalty_record


##-- Get --##
@router.get("/", response_model=list[PenaltyRecordRead])
def list_penalty_records(
    db: Annotated[Session, Depends(get_db)],
    routine_id: Annotated[int | None, Query(description="Filter by routine ID")] = None,
    judge_id: Annotated[int | None, Query(description="Filter by judge ID")] = None,
    judge_role: Annotated[
        PenaltyJudgeRole | None, Query(description="Filter by judge role")
    ] = None,
):
    query = db.query(PenaltyRecord)
    if routine_id is not None:
        query = query.filter(PenaltyRecord.routine_id == routine_id)
    if judge_id is not None:
        query = query.filter(PenaltyRecord.judge_id == judge_id)
    if judge_role is not None:
        query = query.filter(PenaltyRecord.judge_role == judge_role)
    return query.all()


@router.get("/{penalty_record_id}", response_model=PenaltyRecordRead)
def get_penalty_record(penalty_record_id: int, db: Annotated[Session, Depends(get_db)]):
    penalty_record = db.get(PenaltyRecord, penalty_record_id)
    if penalty_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Penalty record with id {penalty_record_id} not found",
        )
    return penalty_record


##-- Patch --##
@router.patch("/{penalty_record_id}", response_model=PenaltyRecordRead)
def update_penalty_record(
    penalty_record_id: int, payload: PenaltyRecordUpdate, db: Annotated[Session, Depends(get_db)]
) -> PenaltyRecord:
    penalty_record = db.get(PenaltyRecord, penalty_record_id)
    if penalty_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Penalty record with id {penalty_record_id} not found",
        )

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(penalty_record, key, value)

    try:
        db.flush()
        _resync_routine_penalty(db, penalty_record.routine)
        db.commit()
        db.refresh(penalty_record)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Integrity error while updating penalty record.",
        ) from e

    return penalty_record


##-- Delete --##
@router.delete("/{penalty_record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_penalty_record(penalty_record_id: int, db: Annotated[Session, Depends(get_db)]):
    penalty_record = db.get(PenaltyRecord, penalty_record_id)
    if penalty_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Penalty record with id {penalty_record_id} not found",
        )

    routine = penalty_record.routine
    db.delete(penalty_record)
    db.flush()
    _resync_routine_penalty(db, routine)
    db.commit()
