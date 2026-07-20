"""
Pydantic schemas for /judges: JudgeCreate/JudgeUpdate/JudgeRead.

country_code is normalized to uppercase and validated as 3-letter alpha
(ISO 3166-1 alpha-3) on both Create and Update.

category is the judge's FIG judging category (JudgeCategory), optional because the
FIG scale only covers brevet holders -- see the Judge model docstring.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import JudgeCategory


class JudgeCreate(BaseModel):
    first_name: str = Field(
        ..., min_length=2, max_length=100, description="The first name of the judge."
    )
    last_name: str = Field(
        ..., min_length=2, max_length=100, description="The last name of the judge."
    )
    country_code: str | None = Field(None, description="The country code of the judge.")
    category: JudgeCategory | None = Field(
        None, description="The judge's FIG judging category (1 highest, 4 lowest)."
    )

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("country_code", mode="before")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        if isinstance(v, str):
            v = v.strip().upper()
            if len(v) != 3 or not v.isalpha():
                raise ValueError("country_code must be a 3-letter ISO 3166-1 alpha-3 country code")
        return v


class JudgeUpdate(BaseModel):
    first_name: str | None = Field(
        None, min_length=2, max_length=100, description="The first name of the judge."
    )
    last_name: str | None = Field(
        None, min_length=2, max_length=100, description="The last name of the judge."
    )
    country_code: str | None = Field(None, description="The country code of the judge.")
    category: JudgeCategory | None = Field(
        None, description="The judge's FIG judging category (1 highest, 4 lowest)."
    )

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("country_code", mode="before")
    @classmethod
    def validate_country_code(cls, v: str | None) -> str | None:
        if isinstance(v, str) and v is not None:
            v = v.strip().upper()
            if len(v) != 3 or not v.isalpha():
                raise ValueError("country_code must be a 3-letter ISO 3166-1 alpha-3 country code")
            return v
        return v


class JudgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    country_code: str | None = None
    category: JudgeCategory | None = None
