from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GymnastCreate(BaseModel):
    # Gymnast can be independent of a club, so club_id is optional
    club_id: int | None = Field(None, ge=1)
    group_id: int | None = Field(None, ge=1)
    first_name: str = Field(..., min_length=2, max_length=100)
    last_name: str = Field(..., min_length=2, max_length=100)
    # Date of birth is optional, may not be known at entry time
    date_of_birth: date | None = None
    # Country is optional an din the format of a 3-letter ISO 3166-1 alpha-3 country code
    country_code: str | None = None

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("country_code", mode="before")
    @classmethod
    def validate_country_code(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip().upper()
            if len(v) != 3 or not v.isalpha():
                raise ValueError("country_code must be a 3-letter ISO 3166-1 alpha-3 country code")
        return v

class GymnastUpdate(BaseModel):
    # Gymnast can be independent of a club, so club_id is optional
    club_id: int | None = Field(None, ge=1)
    group_id: int | None = Field(None, ge=1)
    first_name: str | None = Field(None, min_length=2, max_length=100)
    last_name: str | None = Field(None, min_length=2, max_length=100)
    # Date of birth is optional, may not be known at entry time
    date_of_birth: date | None = None
    # Country is optional an din the format of a 3-letter ISO 3166-1 alpha-3 country code
    country_code: str | None = None

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("country_code", mode="before")
    @classmethod
    def validate_country_code(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip().upper()
            if len(v) != 3 or not v.isalpha():
                raise ValueError("country_code must be a 3-letter ISO 3166-1 alpha-3 country code")
        return v

class GymnastRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    club_id: int | None = None
    group_id: int | None = None
    first_name: str
    last_name: str
    date_of_birth: date | None = None
    country_code: str | None = None
