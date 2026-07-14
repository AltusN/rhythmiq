"""Crud for Club model. /clubs endpoint.

Notes:
    -   POST: explicit get_db(District) to ensure district exists before creating club
        and duplicate chekcs (integrity) after for duplicates
    -   GET: list: optional ?district_id= filter
    -   PATCH: exclude_unset=True so partial updates don't clobber untouched fields
        district_id is intentionally excluded from ClubUpdate - moving a club
        between districts is a domain operation that needs it's own endpoint
    -   DELETE: RESTRICT FK means the DB raises IntegrityError if the club still
        has gymnasts or coaches. Catch that and return 409
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Club, District
from app.schemas.club import ClubCreate, ClubRead, ClubUpdate

router = APIRouter(prefix="/clubs", tags=["Clubs"])


def fetch_club_or_404(db: Session, club_id: int) -> Club:
    """Get a club by ID or raise 404 if not found."""
    club = db.get(Club, club_id)
    if club is None:
        raise HTTPException(status_code=404, detail=f"Club with id {club_id} not found")
    return club


@router.post("/", response_model=ClubRead, status_code=201)
def create_club(payload: ClubCreate, db: Annotated[Session, Depends(get_db)]):
    """Check that district exists before attempting an insert
    This will allow a meaningful error message (404) rather
    than a generic 500 from the DB if the district_id is invalid.
    """
    district = db.get(District, payload.district_id)
    if not district:
        raise HTTPException(
            status_code=404, detail=f"District with id {payload.district_id} not found"
        )

    club = Club(**payload.model_dump())
    # Add the club to the session and commit. IntegrityError will be raised if a duplicate exists.
    db.add(club)
    try:
        db.commit()
        db.refresh(club)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Club with name '{payload.name}' already exists in district {payload.district_id}",
        ) from None

    return club


@router.get("/", response_model=list[ClubRead])
def list_clubs(
    db: Annotated[Session, Depends(get_db)],
    district_id: int | None = Query(
        default=None, description="Optional district_id to filter clubs by district"
    ),
):
    """List all clubs, optionally filtered by district_id"""
    query = db.query(Club)
    if district_id is not None:
        query = query.filter(Club.district_id == district_id)

    return query.all()


@router.get("/{club_id}", response_model=ClubRead)
def get_club(club_id: int, db: Annotated[Session, Depends(get_db)]) -> Club:
    """Get a club by ID."""
    return fetch_club_or_404(db, club_id)


@router.patch("/{club_id}", response_model=ClubRead)
def update_club(club_id: int, payload: ClubUpdate, db: Annotated[Session, Depends(get_db)]) -> Club:
    """Update a club by ID"""
    club = fetch_club_or_404(db, club_id)

    # exclude_unset means only fields the caller actually sent are applied.
    # Sending {} is a valid no-op — nothing changes

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(club, field, value)

    try:
        db.flush()
        db.commit()
        db.refresh(club)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Club with name '{payload.name}' or abbreviation already exists in district {club.district_id}",
        ) from None

    return club


@router.delete("/{club_id}", status_code=204)
def delete_club(club_id: int, db: Annotated[Session, Depends(get_db)]):
    """Delete a club by ID. If the club has gymnasts or coaches, the DB will raise an IntegrityError."""
    club = fetch_club_or_404(db, club_id)

    db.delete(club)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete club with id {club_id} because it has associated gymnasts or coaches",
        ) from None
