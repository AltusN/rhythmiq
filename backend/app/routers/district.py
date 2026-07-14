"""
District Router - CRUD operations for Districts.

-  POST /districts: Create a new district. Returns 201 on success, 409 if a district with the same name or abbreviation already exists.
-  GET /districts: List all districts. Returns 200 with a list of districts.
-  GET /districts/{id}: Get a district by ID. Returns 200 with the district data, or 404 if not found.
-  PATCH /districts/{id}: Update a district by ID. Returns 200 with the updated district data, or 404 if not found, or 409 if the new name or abbreviation conflicts with an existing district.
-  DELETE /districts/{id}: Delete a district by ID. Returns 204 on success, or 404 if not found.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import District
from app.schemas.district import DistrictCreate, DistrictRead, DistrictUpdate

router = APIRouter(prefix="/districts", tags=["Districts"])


@router.post("/", response_model=DistrictRead, status_code=201)
def create_district(payload: DistrictCreate, db: Annotated[Session, Depends(get_db)]):
    district = District(**payload.model_dump())
    db.add(district)
    try:
        db.flush()  # Flush to check for integrity errors before commit
        db.commit()
        db.refresh(district)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"District with name '{payload.name}' or abbreviation '{payload.abbreviation}' already exists",
        ) from None
    return district


@router.get("/", response_model=list[DistrictRead])
def list_districts(db: Annotated[Session, Depends(get_db)]):
    districts = db.query(District).all()
    return districts


@router.get("/{district_id}", response_model=DistrictRead)
def get_district(district_id: int, db: Annotated[Session, Depends(get_db)]):
    district = db.get(District, district_id)
    if district is None:
        raise HTTPException(status_code=404, detail=f"District with id {district_id} not found")
    return district


@router.patch("/{district_id}", response_model=DistrictRead)
def update_district(
    district_id: int, payload: DistrictUpdate, db: Annotated[Session, Depends(get_db)]
):
    district = db.get(District, district_id)
    if district is None:
        raise HTTPException(status_code=404, detail=f"District with id {district_id} not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(district, field, value)

    try:
        db.flush()  # Flush to check for integrity errors before commit
        db.commit()
        db.refresh(district)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"District with name '{payload.name}' or abbreviation '{payload.abbreviation}' already exists",
        ) from None

    return district


@router.delete("/{district_id}", status_code=204)
def delete_district(district_id: int, db: Annotated[Session, Depends(get_db)]):
    district = db.get(District, district_id)
    if district is None:
        raise HTTPException(status_code=404, detail=f"District with id {district_id} not found")

    db.delete(district)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete district with id {district_id} because it has associated clubs",
        ) from None
