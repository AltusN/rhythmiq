"""CRUD for Coaches.

- POST explicit db.get(Club) to ensure club exists before creating coach
- GET list: optional ?club_id= filter
- PATCH: exclude_unset=True so partial updates don't clobber untouched fields
- DELETE: RESTRICT FK means the DB raises IntegrityError if the coach still has gymnasts. Catch that and return 409
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Club, Coach
from app.schemas.coach import CoachCreate, CoachRead, CoachUpdate

router = APIRouter(prefix="/coaches", tags=["Coaches"])


@router.post("/", response_model=CoachRead, status_code=201)
def create_coach(payload: CoachCreate, db: Annotated[Session, Depends(get_db)]):
    """Check that club exists before attempting an insert
    This will allow a meaningful error message (404) rather
    than a generic 500 from the DB if the club_id is invalid.
    """
    club = db.get(Club, payload.club_id)
    if club is None:
        raise HTTPException(status_code=404, detail=f"Club with id {payload.club_id} not found")

    coach = Coach(**payload.model_dump())
    # Add the coach to the session and commit. IntegrityError will be raised if a duplicate exists.
    db.add(coach)
    try:
        db.commit()
        db.refresh(coach)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Coach with name '{payload.first_name} {payload.last_name}' already exists in club {payload.club_id}",
        ) from None

    return coach


@router.get("/", response_model=list[CoachRead])
def list_coaches(
    db: Annotated[Session, Depends(get_db)],
    club_id: int | None = Query(
        default=None, description="Optional club_id to filter coaches by club"
    ),
):
    """List all coaches, optionally filtered by club_id"""
    query = db.query(Coach)
    if club_id is not None:
        query = query.filter(Coach.club_id == club_id)
    return query.all()


@router.get("/{coach_id}", response_model=CoachRead)
def get_coach(coach_id: int, db: Annotated[Session, Depends(get_db)]):
    coach = db.get(Coach, coach_id)
    if coach is None:
        raise HTTPException(status_code=404, detail=f"Coach with id {coach_id} not found")
    return coach


@router.patch("/{coach_id}", response_model=CoachRead)
def update_coach(coach_id: int, payload: CoachUpdate, db: Annotated[Session, Depends(get_db)]):
    coach = db.get(Coach, coach_id)
    if coach is None:
        raise HTTPException(status_code=404, detail=f"Coach with id {coach_id} not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(coach, field, value)

    try:
        db.flush()  # Flush to check for integrity errors before commit
        db.commit()
        db.refresh(coach)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Coach with name '{payload.first_name} {payload.last_name}' already exists in club {coach.club_id}",
        ) from None

    return coach


@router.delete("/{coach_id}", status_code=204)
def delete_coach(coach_id: int, db: Annotated[Session, Depends(get_db)]):
    coach = db.get(Coach, coach_id)
    if coach is None:
        raise HTTPException(status_code=404, detail=f"Coach with id {coach_id} not found")

    db.delete(coach)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete coach with id {coach_id} because they have associated gymnasts",
        ) from None
