from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import MeetStatus


class MeetCreate(BaseModel):
    district_id: int | None = None
    name: str = Field(..., min_length=2, max_length=100)
    location: str = Field(..., min_length=2, max_length=100)
    start_date: date
    end_date: date
    status: MeetStatus = MeetStatus.draft

    # Thought about adding a validator for district id
    # but it's already enforced on the db with the FK
    # a negative value is unlikely and will just result in a 404 from the db,
    #  which is fine. If we want to be more strict, we can add a validator later.

    @field_validator("name", "location", mode="before")
    @classmethod
    def strip_whitespace(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def validate_dates(self) -> "MeetCreate":
        # model validator runs AFTER ALL fields are validated so we have
        # access to both start_date and end_date for comparison.
        # This is the only way to write cross field validation in pydantic v2.

        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValueError("start_date must be on or before end_date")
        return self


class MeetUpdate(BaseModel):
    # Include district_id in update schema to allow changing the district of a meet.
    # from a local meet to a national meet.
    district_id: int | None = None
    name: str | None = Field(None, min_length=2, max_length=100)
    location: str | None = Field(None, min_length=2, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    status: MeetStatus | None = None

    @field_validator("name", "location", mode="before")
    @classmethod
    def strip_whitespace(cls, value: str | None) -> str | None:
        if isinstance(value, str) and value is not None:
            return value.strip()
        return value

    @model_validator(mode="after")
    def validate_dates(self) -> "MeetUpdate":
        # In a partial update, the client may send only one date.
        # We can only validate ordering when BOTH are present in the payload.
        # If only one is sent, the router will compare against the existing
        # DB value — that check belongs in the router, not here.

        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValueError("start_date must be on or before end_date")
        return self


class MeetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    district_id: int | None
    name: str
    location: str
    start_date: date
    end_date: date
    # MeetStatus inherits from str, so it will be serialized as a string in the JSON response.
    status: MeetStatus
