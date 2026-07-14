"""
Pydantic schemas for /groups: GroupCreate/GroupUpdate/GroupRead.

club_id is fixed at creation -- excluded from GroupUpdate, same reasoning as
CoachUpdate/ClubUpdate excluding their parent FK.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GroupCreate(BaseModel):
    club_id: int = Field(..., ge=1)
    name: str = Field(..., min_length=2, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class GroupUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str | None) -> str | None:
        if isinstance(v, str) and v is not None:
            return v.strip()
        return v


class GroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    club_id: int
    name: str
