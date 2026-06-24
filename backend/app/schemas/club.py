from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClubCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    district_id: int
    abbreviation: str = Field(..., min_length=1, max_length=10)

    @field_validator("name", "abbreviation", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("district_id")
    @classmethod
    def validate_district_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("district_id must be a positive integer")
        return v


class ClubUpdate(BaseModel):
    # district_id intentionally excluded: moving a club between districts
    # is a domain-level operation that deserves its own explicit endpoint.
    # i.e. PATCH /clubs/{club_id}/transfer that checks explicit permissions.
    name: str | None = Field(None, min_length=2, max_length=100)
    abbreviation: str | None = Field(None, min_length=1, max_length=10)

    @field_validator("name", "abbreviation", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str | None) -> str | None:
        if isinstance(v, str) and v is not None:
            return v.strip()
        return v


class ClubRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    district_id: int
    abbreviation: str
