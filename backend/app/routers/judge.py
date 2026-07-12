from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Judge
from app.schemas.judge import JudgeCreate, JudgeRead, JudgeUpdate

router = APIRouter(prefix="/judges", tags=["Judges"])


@router.post("/", response_model=JudgeRead, status_code=status.HTTP_201_CREATED)
def create_judge(payload: JudgeCreate, db: Annotated[Session, Depends(get_db)]):
    judge = Judge(**payload.model_dump())
    db.add(judge)

    try:
        db.flush()  # Flush to check for integrity errors before commit
        db.commit()
        db.refresh(judge)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Judge with name '{payload.first_name} {payload.last_name}' from '{payload.country_code}' already exists",
        ) from None
    return judge


@router.get("/", response_model=list[JudgeRead])
def list_judges(
    db: Annotated[Session, Depends(get_db)],
    country_code: str | None = Query(
        default=None,
        description="Optional country_code to filter judges by country",
    ),
):
    """List all judges, optionally filtered by country_code"""
    query = db.query(Judge)
    if country_code is not None:
        query = query.filter(Judge.country_code == country_code)
    return query.all()


@router.get("/{judge_id}", response_model=JudgeRead)
def get_judge(judge_id: int, db: Annotated[Session, Depends(get_db)]):
    judge = db.get(Judge, judge_id)
    if judge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Judge with id {judge_id} not found"
        )
    return judge


@router.patch("/{judge_id}", response_model=JudgeRead)
def update_judge(judge_id: int, payload: JudgeUpdate, db: Annotated[Session, Depends(get_db)]):
    judge = db.get(Judge, judge_id)
    if judge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Judge with id {judge_id} not found"
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(judge, field, value)

    try:
        db.flush()  # Flush to check for integrity errors before commit
        db.commit()
        db.refresh(judge)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Judge with name '{payload.first_name} {payload.last_name}' from '{payload.country_code}' already exists",
        ) from None
    return judge


@router.delete("/{judge_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_judge(judge_id: int, db: Annotated[Session, Depends(get_db)]):
    judge = db.get(Judge, judge_id)
    if judge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Judge with id {judge_id} not found"
        )

    # Judge judge_id has a RESTRICT contraint
    try:
        db.delete(judge)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete Judge with id {judge_id} because it is referenced by other records",
        ) from None
