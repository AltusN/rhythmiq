from pydantic import BaseModel, ConfigDict, Field, field_validator


class CoachCreate(BaseModel):
    first_name: str = Field(..., min_length=2, max_length=100)
    last_name: str = Field(..., min_length=2, max_length=100)
    club_id: int = Field(..., gt=0)
    is_head_coach: bool = False  # optional field, default to False

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class CoachUpdate(BaseModel):
    # Club id is intentionally excluded from the update schema.
    # Reassigning a coach to a different club should be handled through a separate endpoint or process.
    first_name: str | None = Field(None, min_length=2, max_length=100)
    last_name: str | None = Field(None, min_length=2, max_length=100)
    is_head_coach: bool | None = None  # optional field, default to

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            return v.strip()
        return v


class CoachRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    club_id: int
    is_head_coach: bool
