from pydantic import BaseModel, Field, field_validator, ConfigDict

class ClubCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    district_id: int
    abbreviation: str = Field(..., min_length=1, max_length=10)

    @field_validator("name", "abbvreviation", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v
    
class ClubUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    district_id: int | None = None
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