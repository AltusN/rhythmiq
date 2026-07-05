"""
RoutineProfile router — CRUD for /routine-profiles.

Design notes:
- A profile belongs to exactly one of gymnast_id/group_id — enforced by the
  schema's model_validator before the request reaches the router, mirroring
  MeetEntry. POST routes to the right FK check based on which one is set
  (404 if missing) rather than relying on the DB's FK enforcement, which
  isn't guaranteed on outside of test fixtures.
- Uniqueness: two separate UniqueConstraints on the model
  (gymnast_id+apparatus+level, group_id+apparatus+level), so IntegrityError
  -> 409 covers "this gymnast/group already has a profile for this
  apparatus at this level."
- GET filters: ?gymnast_id=, ?group_id=, ?apparatus=, ?level= all make sense
  for looking up a specific profile.
- PATCH: gymnast_id/group_id/apparatus/level are not part of
  RoutineProfileUpdate (locked in at creation, same reasoning as
  MeetEntry/Routine), so no FK pre-check is needed — just exclude_unset.
- DELETE: nothing references RoutineProfile as a parent, so no
  try/except is needed, matching meet_entry.py's delete.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Apparatus, Group, Gymnast, Level, RoutineProfile
from app.schemas.routine_profile import (
    RoutineProfileCreate,
    RoutineProfileRead,
    RoutineProfileUpdate,
)

router = APIRouter(prefix="/routine-profiles", tags=["routine-profiles"])


##-- Post --##
@router.post("/", response_model=RoutineProfileRead, status_code=status.HTTP_201_CREATED)
def create_routine_profile(payload: RoutineProfileCreate, db: Annotated[Session, Depends(get_db)]):
    if payload.gymnast_id is not None:
        gymnast = db.get(Gymnast, payload.gymnast_id)
        if gymnast is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Gymnast with id {payload.gymnast_id} not found",
            )
    else:
        group = db.get(Group, payload.group_id)
        if group is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Group with id {payload.group_id} not found",
            )

    profile = RoutineProfile(**payload.model_dump())
    db.add(profile)

    try:
        db.flush()
        db.commit()
        db.refresh(profile)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Integrity error while creating routine profile.",
        ) from e

    return profile


##-- Get --##
@router.get("/", response_model=list[RoutineProfileRead])
def list_routine_profiles(
    db: Annotated[Session, Depends(get_db)],
    gymnast_id: Annotated[int | None, Query(description="Filter by gymnast_id")] = None,
    group_id: Annotated[int | None, Query(description="Filter by group_id")] = None,
    apparatus: Annotated[Apparatus | None, Query(description="Filter by apparatus")] = None,
    level: Annotated[Level | None, Query(description="Filter by level")] = None,
) -> list[RoutineProfile]:
    query = db.query(RoutineProfile)
    if gymnast_id is not None:
        query = query.filter(RoutineProfile.gymnast_id == gymnast_id)
    if group_id is not None:
        query = query.filter(RoutineProfile.group_id == group_id)
    if apparatus is not None:
        query = query.filter(RoutineProfile.apparatus == apparatus)
    if level is not None:
        query = query.filter(RoutineProfile.level == level)

    return query.all()


@router.get("/{profile_id}", response_model=RoutineProfileRead)
def get_routine_profile(profile_id: int, db: Annotated[Session, Depends(get_db)]) -> RoutineProfile:
    profile = db.get(RoutineProfile, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Routine profile with id {profile_id} not found",
        )
    return profile


##-- Patch --##
@router.patch("/{profile_id}", response_model=RoutineProfileRead)
def update_routine_profile(
    profile_id: int, payload: RoutineProfileUpdate, db: Annotated[Session, Depends(get_db)]
) -> RoutineProfile:
    profile = db.get(RoutineProfile, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Routine profile with id {profile_id} not found",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    try:
        db.flush()
        db.commit()
        db.refresh(profile)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Integrity error while updating routine profile.",
        ) from e

    return profile


##-- Delete --##
@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_routine_profile(profile_id: int, db: Annotated[Session, Depends(get_db)]) -> None:
    profile = db.get(RoutineProfile, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Routine profile with id {profile_id} not found",
        )

    db.delete(profile)
    db.commit()
