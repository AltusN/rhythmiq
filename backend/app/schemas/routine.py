from pydantic import BaseModel, ConfigDict, Field

from app.models import Apparatus


class RoutineCreate(BaseModel):
    entry_id: int = Field(..., description="The ID of the meet entry this routine belongs to.")
    apparatus: Apparatus = Field(..., description="The apparatus for this routine.")
    # order of performance is optional because it may not be known at the time of routine creation
    order_of_performance: int | None = Field(
        None, ge=1, description="The order of performance for this routine."
    )

class RoutineUpdate(BaseModel):
    # entry_id is not updatable because it is a foreign key to the meet entry and should not change after creation
    # it's a domain operation and should be handled by creating a new routine for a different entry if needed
    # apparatus is not updatable because it is a foreign key to the apparatus and should not change after creation
    # if either needs changing, delete and create a new routine instead
    order_of_performance: int | None = Field(
        None, ge=1, description="The order of performance for this routine."
    )

class RoutineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="The unique identifier for this routine.")
    entry_id: int = Field(..., description="The ID of the meet entry this routine belongs to.")
    apparatus: Apparatus = Field(..., description="The apparatus for this routine.")
    order_of_performance: int | None = Field(
        None, description="The order of performance for this routine."
    )
