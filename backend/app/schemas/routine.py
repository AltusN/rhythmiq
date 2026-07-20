"""
Pydantic schemas for /routines: RoutineCreate/RoutineUpdate/RoutineRead, plus
RoutineScoreRead for the read-only GET /routines/{id}/score endpoint.

entry_id/apparatus are excluded from RoutineUpdate -- they're this routine's
identity (its UniqueConstraint), so reassigning either means delete + recreate.
RoutineScoreRead is a separate response shape from RoutineRead because computing
it (compute_routine_score, app/scoring.py) is live and not free -- it's opt-in
via its own endpoint rather than embedded in every plain GET/list.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models import Apparatus


class RoutineCreate(BaseModel):
    entry_id: int = Field(..., description="The ID of the meet entry this routine belongs to.")
    apparatus: Apparatus = Field(..., description="The apparatus for this routine.")
    # order of performance is optional because it may not be known at the time of routine creation
    order_of_performance: int | None = Field(
        None, ge=1, description="The order of performance for this routine."
    )
    # penalty defaults to 0 (matching the column's server_default), not None -- the router's
    # create path builds the model via model_dump() without exclude_unset, so this field must
    # always resolve to a concrete Decimal or it would try to write NULL into a NOT NULL column.
    penalty: Decimal = Field(
        Decimal("0"),
        description="Deduction applied to this routine's final score.",
        ge=0,
        multiple_of=float("0.05"),
    )


class RoutineUpdate(BaseModel):
    # entry_id is not updatable because it is a foreign key to the meet entry and should not change after creation
    # it's a domain operation and should be handled by creating a new routine for a different entry if needed
    # apparatus is not updatable because it is a foreign key to the apparatus and should not change after creation
    # if either needs changing, delete and create a new routine instead
    order_of_performance: int | None = Field(
        None, ge=1, description="The order of performance for this routine."
    )
    penalty: Decimal | None = Field(
        None,
        description="Deduction applied to this routine's final score.",
        ge=0,
        multiple_of=float("0.05"),
    )


class RoutineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="The unique identifier for this routine.")
    entry_id: int = Field(..., description="The ID of the meet entry this routine belongs to.")
    apparatus: Apparatus = Field(..., description="The apparatus for this routine.")
    order_of_performance: int | None = Field(
        None, description="The order of performance for this routine."
    )
    penalty: Decimal = Field(..., description="Deduction applied to this routine's final score.")


class RoutineScoreRead(BaseModel):
    """The live-computed D/A/E/total score for a routine (see app/scoring.py)."""

    routine_id: int = Field(..., description="The ID of the routine this score belongs to.")
    d_score: Decimal = Field(
        ...,
        description="Difficulty score: difficulty_body + difficulty_apparatus subgroups summed.",
    )
    a_score: Decimal = Field(..., description="Artistry score (trimmed mean of artistry marks).")
    e_score: Decimal = Field(..., description="Execution score (trimmed mean of execution marks).")
    final_score: Decimal = Field(
        ...,
        description=(
            "Levels 1-3 only: the single pre-aggregated mark out of 13. 0 at every "
            "other level, where the score is built from the D/A/E panels instead."
        ),
    )
    penalty: Decimal = Field(..., description="Deduction applied to this routine's final score.")
    total: Decimal = Field(..., description="d_score + a_score + e_score - penalty.")
