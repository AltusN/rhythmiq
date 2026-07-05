from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import Apparatus, Level


class RoutineProfileCreate(BaseModel):

    gymnast_id: int | None = Field(None, description="ID of the gymnast associated with the routine profile")
    group_id: int | None = Field(None, description="ID of the group associated with the routine profile")
    apparatus: Apparatus = Field(..., description="Apparatus used in the routine profile")
    level: Level = Field(..., description="Level of the routine profile")
    music_url: str | None = Field(None, description="URL to the music associated with the routine profile")
    choreography_notes: str | None = Field(None, description="Notes about the choreography of the routine profile", max_length=500)

    @model_validator(mode="before")
    @classmethod
    def validate_gymnast_or_group(cls, values: dict) -> dict:
        gymnast_id = values.get("gymnast_id")
        group_id = values.get("group_id")

        if gymnast_id is None and group_id is None:
            raise ValueError("Either gymnast_id or group_id must be provided.")
        if gymnast_id is not None and group_id is not None:
            raise ValueError("Only one of gymnast_id or group_id can be provided.")

        return values

class RoutineProfileUpdate(BaseModel):
    # gymnast_id/group_id/apparatus/level are not updatable here — together they form the
    # model's UniqueConstraints, so reassigning them is a domain operation (delete + recreate),
    # matching the pattern used by MeetEntryUpdate/RoutineUpdate.
    music_url: str | None = Field(None, description="URL to the music associated with the routine profile")
    choreography_notes: str | None = Field(None, description="Notes about the choreography of the routine profile", max_length=500)


class RoutineProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    gymnast_id: int | None
    group_id: int | None
    apparatus: Apparatus
    level: Level
    music_url: str | None
    choreography_notes: str | None
