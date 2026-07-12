from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Judge, JudgeScore, Panel, Routine
from app.schemas.judge_score import JudgeScoreCreate, JudgeScoreRead, JudgeScoreUpdate
from app.scoring import is_panel_valid_for_level

router = APIRouter(prefix="/judge-scores", tags=["Judge Scores"])


##-- Post --##
@router.post("/", response_model=JudgeScoreRead, status_code=status.HTTP_201_CREATED)
def create_judge_score(payload: JudgeScoreCreate, db: Annotated[Session, Depends(get_db)]):
    """
    Create a new judge score.

    Design notes:
    - Levels 1-7 are Execution-only (see app.scoring.E_ONLY_LEVELS) -- a difficulty_body/
      difficulty_apparatus/artistry mark against a routine at one of those levels is
      rejected with a 422, since the payload is invalid for that routine's level, not
      merely in conflict with existing data.
    - Known limitation: this level/panel gate only runs at this HTTP API boundary, since
      it needs a cross-table join (routine -> entry -> level) that a Postgres CHECK
      constraint can't express. Direct ORM writes (test factories, future seed/admin
      scripts) bypass it entirely, unlike ck_judge_score_panel_value_cap which is a real
      DB constraint enforced everywhere.
    """
    routine = db.get(Routine, payload.routine_id)
    if routine is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Routine with id {payload.routine_id} not found",
        )
    if not is_panel_valid_for_level(routine.entry.level, payload.panel):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Routine {payload.routine_id} is level {routine.entry.level.value}, "
                f"which is scored on execution only -- {payload.panel.value} is not valid."
            ),
        )
    judge = db.get(Judge, payload.judge_id)
    if judge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Judge with id {payload.judge_id} not found",
        )

    judge_score = JudgeScore(**payload.model_dump())
    db.add(judge_score)

    try:
        db.flush()
        db.commit()
        db.refresh(judge_score)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Judge {payload.judge_id} has already submitted a {payload.panel.value} "
                f"score for routine {payload.routine_id}"
            ),
        ) from e

    return judge_score


##-- Get --##
@router.get("/", response_model=list[JudgeScoreRead])
def list_judge_scores(
    db: Annotated[Session, Depends(get_db)],
    routine_id: Annotated[int | None, Query(description="Filter by routine ID")] = None,
    judge_id: Annotated[int | None, Query(description="Filter by judge ID")] = None,
    panel: Annotated[Panel | None, Query(description="Filter by panel")] = None,
):
    query = db.query(JudgeScore)
    if routine_id is not None:
        query = query.filter(JudgeScore.routine_id == routine_id)
    if judge_id is not None:
        query = query.filter(JudgeScore.judge_id == judge_id)
    if panel is not None:
        query = query.filter(JudgeScore.panel == panel)
    return query.all()


@router.get("/{judge_score_id}", response_model=JudgeScoreRead)
def get_judge_score(judge_score_id: int, db: Annotated[Session, Depends(get_db)]):
    judge_score = db.get(JudgeScore, judge_score_id)
    if judge_score is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Judge score with id {judge_score_id} not found",
        )
    return judge_score


##-- Patch --##
@router.patch("/{judge_score_id}", response_model=JudgeScoreRead)
def update_judge_score(
    judge_score_id: int, payload: JudgeScoreUpdate, db: Annotated[Session, Depends(get_db)]
) -> JudgeScore:
    judge_score = db.get(JudgeScore, judge_score_id)
    if judge_score is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Judge score with id {judge_score_id} not found",
        )

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(judge_score, key, value)

    try:
        db.flush()
        db.commit()
        db.refresh(judge_score)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Value {payload.value} is not valid for judge score {judge_score_id} "
                "(artistry/execution scores cannot exceed 10.0)"
            ),
        ) from e

    return judge_score


##-- Delete --##
@router.delete("/{judge_score_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_judge_score(judge_score_id: int, db: Annotated[Session, Depends(get_db)]):
    judge_score = db.get(JudgeScore, judge_score_id)
    if judge_score is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Judge score with id {judge_score_id} not found",
        )

    db.delete(judge_score)
    db.commit()
