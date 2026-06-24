from pydantic import BaseModel, ConfigDict, Field

from app.models import AgeGroup, Level


class MeetEntryCreate(BaseModel):
    meet_id: int = Field(..., description="The ID of the meet")
    gymnast_id: int = Field(..., description="The ID of the gymnast")
    level: Level = Field(..., description="The level of the gymnast")
    age_group: AgeGroup = Field(..., description="The age group of the gymnast")
    bib_number: str | None = Field(None, description="The bib number of the gymnast")
    entry_fee_paid: bool = Field(False, description="Whether the entry fee has been paid")


class MeetEntryUpdate(BaseModel):
    # meet id and gymnast_id are not updatable here. Reasoning: If you want to change the meet or gymnast, you should delete the entry and create a new one.
    # shoudl be handled as a domain event
    level: Level | None = Field(None, description="The level of the gymnast")
    age_group: AgeGroup | None = Field(None, description="The age group of the gymnast")
    bib_number: str | None = Field(None, description="The bib number of the gymnast")
    entry_fee_paid: bool | None = Field(None, description="Whether the entry fee has been paid")


class MeetEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="The ID of the meet entry")
    meet_id: int = Field(..., description="The ID of the meet")
    gymnast_id: int = Field(..., description="The ID of the gymnast")
    level: Level = Field(..., description="The level of the gymnast")
    age_group: AgeGroup = Field(..., description="The age group of the gymnast")
    bib_number: str | None = Field(None, description="The bib number of the gymnast")
    entry_fee_paid: bool = Field(..., description="Whether the entry fee has been paid")
