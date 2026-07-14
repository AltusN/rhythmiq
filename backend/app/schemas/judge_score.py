"""
Pydantic schemas for /judge-scores: JudgeScoreCreate/JudgeScoreUpdate/JudgeScoreRead.

JudgeScoreCreate enforces the artistry/execution <= 10 cap (CAPPED_PANELS) that's
mirrored in the DB by ck_judge_score_panel_value_cap. The level-dependent panel
gate (e.g. no difficulty panels below level_8) can't be checked here -- it needs a
routine -> entry -> level join this schema has no access to -- so that lives in
app/routers/judge_score.py instead.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import Panel

CAPPED_PANELS = {Panel.artistry, Panel.execution}


class JudgeScoreCreate(BaseModel):
    routine_id: int = Field(..., description="The ID of the routine being scored")
    judge_id: int = Field(..., description="The ID of the judge submitting the score")
    panel: Panel = Field(..., description="The panel of the judge submitting the score")
    value: Decimal = Field(
        ..., description="The score value being submitted", ge=0, multiple_of=float("0.05")
    )

    @model_validator(mode="after")
    def validate_score_cap(self) -> "JudgeScoreCreate":
        if self.panel in CAPPED_PANELS and self.value > 10:
            raise ValueError("Artistry and execution scores cannot exceed 10.0")
        return self


class JudgeScoreUpdate(BaseModel):
    # routine_id/judge_id/panel are not updatable -- they're this score's identity
    # (and the UniqueConstraint on them), matching MeetEntry/Routine's
    # delete + recreate pattern. The panel-dependent cap is enforced by the
    # ck_judge_score_panel_value_cap DB constraint instead, since panel isn't
    # part of this payload to validate against here.
    value: Decimal | None = Field(
        None, description="The score value being updated", ge=0, multiple_of=float("0.05")
    )


class JudgeScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    routine_id: int
    judge_id: int
    panel: Panel
    value: Decimal
