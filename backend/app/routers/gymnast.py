"""
Gymnast router — CRUD for /gymnasts.

Design notes:
- POST: club_id is nullable, so only pre-check the club if club_id is
  provided. club_id=None means an independent gymnast — always valid.
- PATCH: club_id is included in GymnastUpdate (unlike CoachUpdate).
  If the update contains a non-None club_id, we verify that club exists
  before applying. Setting club_id=None makes the gymnast independent.
- DELETE: cascades to MeetEntry/Routine via the ORM. No RESTRICT concern.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Club, Gymnast
from app.schemas.gymnast import GymnastCreate, GymnastRead, GymnastUpdate

router = APIRouter(prefix="/gymnasts", tags=["gymnasts"])

@router.post("/", response_model=GymnastRead, status_code=status.HTTP_201_CREATED)
def create_gymnast(payload: GymnastCreate, db: Annotated[Session, Depends(get_db)]):
    if payload.club_id is not None:
        club = db.get(Club, payload.club_id)
        if club is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Club with id {payload.club_id} not found")

    gymnast = Gymnast(**payload.model_dump())
    db.add(gymnast)
    try:
        db.flush()  # Flush to check for integrity errors before commit
        db.commit()
        db.refresh(gymnast)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Gymnast with name '{payload.first_name} {payload.last_name}' already exists"
        ) from None
    return gymnast

@router.get("/", response_model=list[GymnastRead])
def list_gymnasts(
    db: Annotated[Session, Depends(get_db)],
    club_id: int | None = Query(None, description="Filter by club ID"),
):
    if club_id is not None:
        gymnasts = db.query(Gymnast).filter(Gymnast.club_id == club_id).all()
    else:
        gymnasts = db.query(Gymnast).all()
    return gymnasts

@router.get("/{gymnast_id}", response_model=GymnastRead)
def get_gymnast(gymnast_id: int, db: Annotated[Session, Depends(get_db)]):
    gymnast = db.get(Gymnast, gymnast_id)
    if gymnast is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Gymnast with id {gymnast_id} not found")
    return gymnast

@router.patch("/{gymnast_id}", response_model=GymnastRead)
def update_gymnast(gymnast_id: int, payload: GymnastUpdate, db: Annotated[Session, Depends(get_db)]):
    gymnast = db.get(Gymnast, gymnast_id)
    if gymnast is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Gymnast with id {gymnast_id} not found")

    if payload.club_id is not None:
        club = db.get(Club, payload.club_id)
        if club is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Club with id {payload.club_id} not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(gymnast, field, value)

    try:
        db.flush()  # Flush to check for integrity errors before commit
        db.commit()
        db.refresh(gymnast)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Gymnast with name '{payload.first_name} {payload.last_name}' already exists"
        ) from None
    return gymnast

@router.delete("/{gymnast_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gymnast(gymnast_id: int, db: Annotated[Session,  Depends(get_db)]):
    gymnast = db.get(Gymnast, gymnast_id)
    if gymnast is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Gymnast with id {gymnast_id} not found")

    db.delete(gymnast)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete gymnast with id {gymnast_id} due to existing references"
        ) from None

