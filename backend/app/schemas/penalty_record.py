from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models import PenaltyJudgeRole


class PenaltyRecordCreate(BaseModel):
    routine_id: int = Field(..., description="The ID of the routine being penalized")
    judge_id: int = Field(..., description="The ID of the judge assessing the penalty")
    judge_role: PenaltyJudgeRole = Field(..., description="Which judge role assessed this penalty")
    description: str = Field(..., min_length=1, description="What happened (e.g. 'boundary touch')")
    amount: Decimal = Field(
        ..., description="The penalty amount deducted", gt=0, multiple_of=float("0.05")
    )


class PenaltyRecordUpdate(BaseModel):
    # routine_id/judge_id are not updatable -- they're this record's identity, matching
    # JudgeScore's delete + recreate pattern. judge_role IS updatable here (unlike
    # JudgeScore.panel), since PenaltyRecord has no uniqueness constraint tying
    # judge_role to routine_id/judge_id -- it's a plain descriptive field, not identity.
    judge_role: PenaltyJudgeRole | None = Field(
        None, description="Which judge role assessed this penalty"
    )
    description: str | None = Field(
        None, min_length=1, description="What happened (e.g. 'boundary touch')"
    )
    amount: Decimal | None = Field(
        None, description="The penalty amount deducted", gt=0, multiple_of=float("0.05")
    )


class PenaltyRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    routine_id: int
    judge_id: int
    judge_role: PenaltyJudgeRole
    description: str
    amount: Decimal
