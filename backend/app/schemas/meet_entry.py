"""
Pydantic schemas for /meet-entries: MeetEntryCreate/MeetEntryUpdate/MeetEntryRead.

MeetEntryCreate enforces exactly one of gymnast_id/group_id via
validate_gymnast_or_group, mirroring the model's
ck_meet_entry_gymnast_or_group_not_null CheckConstraint. meet_id/gymnast_id/
group_id are all excluded from MeetEntryUpdate -- reassigning any of them is a
delete-and-recreate, not an editable field.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import AgeGroup, Level


class MeetEntryCreate(BaseModel):
    meet_id: int = Field(..., description="The ID of the meet")
    # Exactly one of gymnast_id/group_id must be set — mirrors the
    # ck_meet_entry_gymnast_or_group_not_null CheckConstraint on the model.
    gymnast_id: int | None = Field(None, description="The ID of the gymnast")
    group_id: int | None = Field(None, description="The ID of the group")
    level: Level = Field(..., description="The level of the gymnast")
    age_group: AgeGroup = Field(..., description="The age group of the gymnast")
    # bib_number is required — the model column is NOT NULL.
    bib_number: str = Field(..., description="The bib number of the gymnast")
    entry_fee_paid: bool = Field(False, description="Whether the entry fee has been paid")

    @field_validator("bib_number", mode="before")
    @classmethod
    def strip_whitespace(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def validate_gymnast_or_group(self) -> "MeetEntryCreate":
        if (self.gymnast_id is None) == (self.group_id is None):
            raise ValueError("Exactly one of gymnast_id or group_id must be set")
        return self


class MeetEntryUpdate(BaseModel):
    # meet id, gymnast_id and group_id are not updatable here. Reasoning: If you want to change
    # the meet or participant, you should delete the entry and create a new one.
    # shoudl be handled as a domain event
    level: Level | None = Field(None, description="The level of the gymnast")
    age_group: AgeGroup | None = Field(None, description="The age group of the gymnast")
    bib_number: str | None = Field(None, description="The bib number of the gymnast")
    entry_fee_paid: bool | None = Field(None, description="Whether the entry fee has been paid")

    @field_validator("bib_number", mode="before")
    @classmethod
    def strip_whitespace(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip()
        return value


class MeetEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="The ID of the meet entry")
    meet_id: int = Field(..., description="The ID of the meet")
    gymnast_id: int | None = Field(None, description="The ID of the gymnast")
    group_id: int | None = Field(None, description="The ID of the group")
    level: Level = Field(..., description="The level of the gymnast")
    age_group: AgeGroup = Field(..., description="The age group of the gymnast")
    bib_number: str | None = Field(None, description="The bib number of the gymnast")
    entry_fee_paid: bool = Field(..., description="Whether the entry fee has been paid")
