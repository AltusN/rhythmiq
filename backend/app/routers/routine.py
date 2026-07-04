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
  RoutineUpdate) — only order_of_performance changes, so no FK pre-check
  needed.
- DELETE: nothing references Routine as a parent, so no IntegrityError can
  occur — no try/except needed, matching meet_entry.py's delete.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import MeetEntry, Routine
from app.schemas.routine import RoutineCreate, RoutineRead, RoutineUpdate

router = APIRouter(prefix="/routines", tags=["routines"])


##-- Post --##
@router.post("/", response_model=RoutineRead, status_code=status.HTTP_201_CREATED)
def create_routine(payload: RoutineCreate, db: Annotated[Session, Depends(get_db)]):
    entry = db.get(MeetEntry, payload.entry_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meet entry with id {payload.entry_id} not found",
        )

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

    for field, value in payload.model_dump(exclude_unset=True).items():
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

    db.delete(routine)
    db.commit()
