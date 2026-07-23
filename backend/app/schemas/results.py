"""
Response schemas for GET /meets/{id}/standings and /meets/{id}/all-around
(app/routers/results.py). Read-only -- there's no Create/Update here since these
are computed views, not a stored resource.
"""

from decimal import Decimal

from pydantic import BaseModel, Field

from app.models import AgeGroup, Apparatus, Level
from app.scoring import Medal


class ApparatusStandingRow(BaseModel):
    rank: int = Field(..., description="Competition rank within this apparatus category.")
    entry_id: int = Field(..., description="The meet entry this routine belongs to.")
    routine_id: int = Field(..., description="The routine this row represents.")
    competitor_name: str = Field(..., description="Gymnast full name, or group name.")
    bib_number: str = Field(..., description="Bib number of the competing entry.")
    level: Level
    age_group: AgeGroup
    apparatus: Apparatus
    d_score: Decimal
    a_score: Decimal
    e_score: Decimal
    final_score: Decimal = Field(
        ...,
        description=(
            "Levels 1-3 only: the trimmed mean of the panel's final marks (each out "
            "of 13). 0 at every other level, where the score is built from the D/A/E "
            "panels instead."
        ),
    )
    penalty: Decimal
    total: Decimal
    medal: Medal | None = Field(
        None,
        description=(
            "Standard-based medal tier from the meet's configured cutoffs "
            "(Meet.medal_gold_min/medal_silver_min), independent of rank. "
            "Null if the meet isn't using cutoffs."
        ),
    )


class ApparatusStandingsRead(BaseModel):
    """Live-computed per-apparatus ranking for one meet/level/age_group/apparatus slice."""

    meet_id: int
    provisional: bool = Field(..., description="True unless the meet's status is 'completed'.")
    apparatus: Apparatus
    level: Level | None = Field(None, description="Level filter applied, if any.")
    age_group: AgeGroup | None = Field(None, description="Age group filter applied, if any.")
    rankings: list[ApparatusStandingRow]


class AllAroundStandingRow(BaseModel):
    rank: int = Field(..., description="Competition rank within this all-around category.")
    entry_id: int = Field(..., description="The meet entry this row represents.")
    competitor_name: str = Field(..., description="Gymnast full name, or group name.")
    bib_number: str = Field(..., description="Bib number of the competing entry.")
    level: Level
    age_group: AgeGroup
    total: Decimal = Field(..., description="Sum of this entry's routine totals.")
    e_total: Decimal = Field(..., description="Sum of this entry's routine Execution scores.")
    routines_counted: int = Field(
        ...,
        description="Number of routines summed -- less than the full apparatus count means a partial (in-progress or incomplete) all-around.",
    )
    medal: Medal | None = Field(
        None,
        description=(
            "Standard-based medal tier from the meet's configured cutoffs "
            "(Meet.medal_gold_min/medal_silver_min), independent of rank. "
            "Null if the meet isn't using cutoffs."
        ),
    )


class AllAroundStandingsRead(BaseModel):
    """Live-computed all-around ranking for one meet/level/age_group slice."""

    meet_id: int
    provisional: bool = Field(..., description="True unless the meet's status is 'completed'.")
    level: Level | None = Field(None, description="Level filter applied, if any.")
    age_group: AgeGroup | None = Field(None, description="Age group filter applied, if any.")
    rankings: list[AllAroundStandingRow]
