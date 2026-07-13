"""
Meet router — CRUD for /meets.

Design notes:
- POST: district_id is nullable (None = national/open meet). Pre-check
  only if not None. IntegrityError → 409.
- PATCH dates: the schema model_validator only fires when both dates are
  present in the payload. When only one date is sent, the router fetches
  the stored record and validates the incoming value against the existing
  counterpart date.
- PATCH status: forward-only transitions are enforced via an allowed-
  transitions map. Any status → cancelled is always permitted (besides in_progress).
  This will cause a conflict if attempted.
  Sending the current status is a no-op (not an error).
- PATCH medal cutoffs: same split as dates -- the schema validates ordering when
  both medal_gold_min/medal_silver_min are sent together, but a partial update may
  send only one (to change it while leaving the other as stored), so the router
  re-checks the "both or neither" + ordering invariant against the stored value.
- DELETE: cascades to MeetEntry/Routine via ORM (no RESTRICT concern), but
  blocked (409) for in_progress or completed meets — an in_progress meet
  has live state you don't want to yank out from under it, and a completed
  meet is the historical record of who competed and on what apparatus;
  deleting it would silently erase that history with no recovery path.
"""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import District, Meet, MeetStatus
from app.schemas.meet import MeetCreate, MeetRead, MeetUpdate

router = APIRouter(prefix="/meets", tags=["Meets"])

# Transition map for MeetStatus
ALLOWED_STATUS_TRANSITIONS: dict[MeetStatus, set[MeetStatus]] = {
    MeetStatus.draft: {MeetStatus.scheduled, MeetStatus.cancelled},
    MeetStatus.scheduled: {MeetStatus.in_progress, MeetStatus.cancelled},
    MeetStatus.in_progress: {MeetStatus.completed, MeetStatus.cancelled},
    MeetStatus.completed: set(),
    MeetStatus.cancelled: set(),
}


def _validate_status_transition(current: MeetStatus, new: MeetStatus) -> None:
    if current == new:
        return  # No-op
    allowed = ALLOWED_STATUS_TRANSITIONS.get(current, set())
    if new not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid status transition from {current.value} to {new.value}.",
        )


def _validate_partial_dates(
    incoming_start: date | None, incoming_end: date | None, stored_start: date, stored_end: date
) -> None:
    """
    Validate incoming start/end dates against stored values.
    Raises HTTPException if invalid. the schema already validates
    if both dates are present, so this is only for partial updates.
    """
    effective_start = incoming_start if incoming_start is not None else stored_start
    effective_end = incoming_end if incoming_end is not None else stored_end

    if effective_end < effective_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="end_date cannot be before start_date.",
        )


def _validate_partial_medal_cutoffs(
    gold_sent: bool,
    silver_sent: bool,
    incoming_gold: Decimal | None,
    incoming_silver: Decimal | None,
    stored_gold: Decimal | None,
    stored_silver: Decimal | None,
) -> None:
    """
    Validate incoming medal cutoffs against stored values. The schema already
    validates ordering when both are present in this payload; here we cover the
    "only one sent" case by resolving each field to its incoming value if sent,
    or the stored value otherwise, then re-checking both-or-neither + ordering.
    """
    effective_gold = incoming_gold if gold_sent else stored_gold
    effective_silver = incoming_silver if silver_sent else stored_silver

    if (effective_gold is None) != (effective_silver is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="medal_gold_min and medal_silver_min must be set together.",
        )
    if (
        effective_gold is not None
        and effective_silver is not None
        and effective_gold <= effective_silver
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="medal_gold_min must be greater than medal_silver_min.",
        )


##-- Post --##
@router.post("/", response_model=MeetRead, status_code=status.HTTP_201_CREATED)
def create_meet(payload: MeetCreate, db: Annotated[Session, Depends(get_db)]):
    if payload.district_id is not None:
        district = db.get(District, payload.district_id)
        if district is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"District with id {payload.district_id} not found",
            )

    meet = Meet(**payload.model_dump())
    db.add(meet)

    try:
        db.flush()
        db.commit()
        db.refresh(meet)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Integrity error while creating meet."
        ) from e

    return meet


##-- Get --##
@router.get("/", response_model=list[MeetRead])
def list_meets(
    db: Annotated[Session, Depends(get_db)],
    district_id: Annotated[int | None, Query(description="Filter by district_id")] = None,
    status: Annotated[MeetStatus | None, Query(description="Filter by status")] = None,
) -> list[Meet]:
    query = db.query(Meet)
    if district_id is not None:
        query = query.filter(Meet.district_id == district_id)
    if status is not None:
        query = query.filter(Meet.status == status)

    return query.all()


@router.get("/{meet_id}", response_model=MeetRead)
def get_meet(meet_id: int, db: Annotated[Session, Depends(get_db)]) -> Meet:
    meet = db.get(Meet, meet_id)
    if not meet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meet not found")
    return meet


##-- Patch --##
@router.patch("/{meet_id}", response_model=MeetRead)
def update_meet(meet_id: int, payload: MeetUpdate, db: Annotated[Session, Depends(get_db)]) -> Meet:
    meet = db.get(Meet, meet_id)
    if not meet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Meet {meet_id} not found"
        )

    updates = payload.model_dump(exclude_unset=True)

    # district_id... only validate if set
    if "district_id" in updates:
        district_id = updates["district_id"]
        if district_id is not None:
            district = db.get(District, district_id)
            if district is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"District with id {district_id} not found",
                )

    # Date validation: if both dates are present, the schema validator already checks.
    # If only one is present, we need to validate against the stored value.

    incoming_start = updates.get("start_date")
    incoming_end = updates.get("end_date")
    if incoming_start is not None or incoming_end is not None:
        _validate_partial_dates(
            incoming_start=incoming_start,
            incoming_end=incoming_end,
            stored_start=meet.start_date,
            stored_end=meet.end_date,
        )

    # Status transition validation
    if "status" in updates:
        new_status = updates["status"]
        _validate_status_transition(current=meet.status, new=new_status)

    # Medal cutoff validation: if either field is in this payload, re-check
    # both-or-neither + ordering against whatever isn't being changed.
    if "medal_gold_min" in updates or "medal_silver_min" in updates:
        _validate_partial_medal_cutoffs(
            gold_sent="medal_gold_min" in updates,
            silver_sent="medal_silver_min" in updates,
            incoming_gold=updates.get("medal_gold_min"),
            incoming_silver=updates.get("medal_silver_min"),
            stored_gold=meet.medal_gold_min,
            stored_silver=meet.medal_silver_min,
        )

    for field, value in updates.items():
        setattr(meet, field, value)

    try:
        db.flush()
        db.commit()
        db.refresh(meet)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Integrity error while updating meet."
        ) from e

    return meet


@router.delete("/{meet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meet(meet_id: int, db: Annotated[Session, Depends(get_db)]) -> None:
    meet = db.get(Meet, meet_id)
    if not meet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meet not found")

    if meet.status == MeetStatus.in_progress:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Cannot delete a meet that is in progress"
        )
    if meet.status == MeetStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Cannot delete a meet that is completed"
        )

    db.delete(meet)
    db.commit()
