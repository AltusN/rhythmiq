"""
MeetEntry router — CRUD for /meet-entries.

Design notes:
- A meet entry belongs to either a gymnast or a group, never both. The
  schema's model_validator already guarantees exactly one of
  gymnast_id/group_id arrived, so the router doesn't need to re-check
  that — just route to the right FK check based on which one is present.
- POST: meet_id is always checked (404 if missing). If gymnast_id is set,
  check Gymnast exists; if group_id is set, check Group exists.
- Uniqueness: two separate UniqueConstraints on the model
  (meet_id+gymnast_id, meet_id+group_id), so IntegrityError → 409 covers
  "this gymnast/group already has an entry at this meet."
- GET filters: ?meet_id=, ?gymnast_id=, ?group_id=, ?level=, ?age_group= are all
  optional, and can be combined. If none are provided, returns all meet entries.
- PATCH: no FK fields are updatable at all (locked in), so it's the
  simplest PATCH we've written — no FK pre-checks needed, just
  exclude_unset + IntegrityError → 409.
- DELETE: cascades to Routine via the ORM (cascade="all, delete-orphan"
  already on the model). Clean delete, no RESTRICT.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Group, Gymnast, Meet, MeetEntry
from app.schemas.meet_entry import MeetEntryCreate, MeetEntryRead, MeetEntryUpdate

router = APIRouter(prefix="/meet-entries", tags=["meet-entries"])

##-- Post --##
@router.post("/", response_model=MeetEntryRead, status_code=status.HTTP_201_CREATED)
def create_meet_entry(payload: MeetEntryCreate, db: Annotated[Session, Depends(get_db)]):
    meet = db.get(Meet, payload.meet_id)
    if meet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meet with id {payload.meet_id} not found")

    if payload.gymnast_id is not None:
        gymnast = db.get(Gymnast, payload.gymnast_id)
        if gymnast is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Gymnast with id {payload.gymnast_id} not found")
    else:
        group = db.get(Group, payload.group_id)
        if group is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Group with id {payload.group_id} not found")

    entry = MeetEntry(**payload.model_dump())
    db.add(entry)

    try:
        db.flush()
        db.commit()
        db.refresh(entry)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Integrity error while creating meet entry.") from e

    return entry

##-- Get --##
@router.get("/", response_model=list[MeetEntryRead])
def list_meet_entries(
    db: Annotated[Session, Depends(get_db)],
    meet_id: Annotated[int | None, Query(description="Filter by meet_id")] = None,
    gymnast_id: Annotated[int | None, Query(description="Filter by gymnast_id")] = None,
    group_id: Annotated[int | None, Query(description="Filter by group_id")] = None,
    level: Annotated[str | None, Query(description="Filter by level")] = None,
    age_group: Annotated[str | None, Query(description="Filter by age_group")] = None,
) -> list[MeetEntry]:
    query = db.query(MeetEntry)
    if meet_id is not None:
        query = query.filter(MeetEntry.meet_id == meet_id)
    if gymnast_id is not None:
        query = query.filter(MeetEntry.gymnast_id == gymnast_id)
    if group_id is not None:
        query = query.filter(MeetEntry.group_id == group_id)
    if level is not None:
        query = query.filter(MeetEntry.level == level)
    if age_group is not None:
        query = query.filter(MeetEntry.age_group == age_group)
    return query.all()

@router.get("/{entry_id}", response_model=MeetEntryRead)
def get_meet_entry(entry_id: int, db: Annotated[Session, Depends(get_db)]) -> MeetEntry:
    entry = db.get(MeetEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meet entry not found")
    return entry

##-- Patch --##
@router.patch("/{entry_id}", response_model=MeetEntryRead)
def update_meet_entry(entry_id: int, payload: MeetEntryUpdate, db: Annotated[Session, Depends(get_db)]) -> MeetEntry:
    entry = db.get(MeetEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meet entry {entry_id} not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)

    try:
        db.flush()
        db.commit()
        db.refresh(entry)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Integrity error while updating meet entry.") from e

    return entry

##-- Delete --##
@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meet_entry(entry_id: int, db: Annotated[Session, Depends(get_db)]) -> None:
    entry = db.get(MeetEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meet entry not found")

    db.delete(entry)
    db.commit()
