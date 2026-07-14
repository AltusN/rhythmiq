"""
Pydantic schemas for /districts: DistrictCreate/DistrictUpdate/DistrictRead.

abbreviation is normalized to uppercase on both Create and Update, matching Club's
convention.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DistrictCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    abbreviation: str = Field(..., min_length=1, max_length=10)

    @field_validator("name", "abbreviation", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("abbreviation", mode="before")
    @classmethod
    def to_uppercase(cls, v: str) -> str:
        if isinstance(v, str):
            return v.upper()
        return v


class DistrictUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    abbreviation: str | None = Field(None, min_length=1, max_length=10)

    @field_validator("name", "abbreviation", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str | None) -> str | None:
        if isinstance(v, str) and v is not None:
            return v.strip()
        return v

    @field_validator("abbreviation", mode="before")
    @classmethod
    def to_uppercase(cls, v: str | None) -> str | None:
        if isinstance(v, str) and v is not None:
            return v.upper()
        return v


class DistrictRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    abbreviation: str
