"""
Pydantic validation tests for the MeetCreate/MeetUpdate/MeetRead schemas, including
the start_date <= end_date model_validator (only fires when both dates are present)
and the medal_gold_min/medal_silver_min cutoff validator (same both-present split).
"""

import pytest
from pydantic import ValidationError

from app.models import MeetStatus
from app.schemas.meet import MeetCreate, MeetRead, MeetUpdate


class TestMeetCreate:
    def test_meet_create_allows_missing_district_id(self):
        meet = MeetCreate.model_validate(
            {
                "name": "Nationals",
                "location": "Main Arena",
                "start_date": "2026-06-01",
                "end_date": "2026-06-02",
            }
        )

        assert meet.district_id is None
        assert meet.status == MeetStatus.draft  # Default status should be 'draft'

    def test_meet_create_accepts_district_id(self):
        meet = MeetCreate.model_validate(
            {
                "district_id": 3,
                "name": "District Meet",
                "location": "Main Arena",
                "start_date": "2026-06-01",
                "end_date": "2026-06-02",
            }
        )

        assert meet.district_id == 3

    def test_meet_create_district_can_be_null(self):
        MeetCreate.model_validate(
            {
                "district_id": None,
                "name": "Invalid Meet",
                "location": "Main Arena",
                "start_date": "2026-06-01",
                "end_date": "2026-06-02",
            }
        )

    def test_meet_create_medal_cutoffs_default_to_none(self):
        meet = MeetCreate.model_validate(
            {
                "name": "Nationals",
                "location": "Main Arena",
                "start_date": "2026-06-01",
                "end_date": "2026-06-02",
            }
        )

        assert meet.medal_gold_min is None
        assert meet.medal_silver_min is None

    def test_meet_create_medal_cutoffs_valid_pair_accepted(self):
        meet = MeetCreate.model_validate(
            {
                "name": "Club Meet",
                "location": "Main Arena",
                "start_date": "2026-06-01",
                "end_date": "2026-06-02",
                "medal_gold_min": "24.00",
                "medal_silver_min": "20.00",
            }
        )

        assert meet.medal_gold_min == 24
        assert meet.medal_silver_min == 20

    @pytest.mark.parametrize(
        "medal_gold_min, medal_silver_min",
        [
            ("24.00", None),
            (None, "20.00"),
            ("20.00", "20.00"),
            ("18.00", "20.00"),
        ],
    )
    def test_meet_create_medal_cutoffs_invalid_combinations_rejected(
        self, medal_gold_min, medal_silver_min
    ):
        with pytest.raises(ValidationError):
            MeetCreate.model_validate(
                {
                    "name": "Club Meet",
                    "location": "Main Arena",
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-02",
                    "medal_gold_min": medal_gold_min,
                    "medal_silver_min": medal_silver_min,
                }
            )


class TestMeetUpdate:
    def test_meet_update_all_fields_optional(self):
        meet = MeetUpdate.model_validate({})

        assert meet.district_id is None
        assert meet.name is None
        assert meet.location is None
        assert meet.start_date is None
        assert meet.end_date is None
        assert meet.status is None

    def test_meet_update_accepts_district_id(self):
        meet = MeetUpdate.model_validate({"district_id": 5})

        assert meet.district_id == 5

    def test_meet_update_accepts_null_district_id(self):
        meet = MeetUpdate.model_validate({"district_id": None})
        assert meet.district_id is None

    def test_meet_update_medal_cutoffs_both_optional(self):
        meet = MeetUpdate.model_validate({})
        assert meet.medal_gold_min is None
        assert meet.medal_silver_min is None

    def test_meet_update_medal_cutoffs_valid_pair_accepted(self):
        meet = MeetUpdate.model_validate({"medal_gold_min": "24.00", "medal_silver_min": "20.00"})
        assert meet.medal_gold_min == 24
        assert meet.medal_silver_min == 20

    def test_meet_update_medal_cutoffs_gold_not_greater_than_silver_rejected(self):
        with pytest.raises(ValidationError):
            MeetUpdate.model_validate({"medal_gold_min": "20.00", "medal_silver_min": "20.00"})

    def test_meet_update_medal_cutoffs_one_sent_alone_not_rejected_by_schema(self):
        # Only one field is present in this payload, so the schema defers the
        # both-or-neither check to the router (which compares against stored values).
        meet = MeetUpdate.model_validate({"medal_gold_min": "24.00"})
        assert meet.medal_gold_min == 24
        assert meet.medal_silver_min is None


class TestMeetRead:
    def test_meet_read_from_mapping(self):
        meet = MeetRead.model_validate(
            {
                "id": 1,
                "district_id": None,
                "name": "Nationals",
                "location": "Main Arena",
                "start_date": "2026-06-01",
                "end_date": "2026-06-02",
                "status": MeetStatus.scheduled,
                "medal_gold_min": None,
                "medal_silver_min": None,
            }
        )

        assert meet.id == 1
        assert meet.district_id is None
        assert meet.status == MeetStatus.scheduled

    def test_meet_read_from_orm_like_object(self):
        class ORMObject:
            def __init__(self):
                self.id = 1
                self.district_id = 7
                self.name = "District Meet"
                self.location = "Main Arena"
                self.start_date = "2026-06-01"
                self.end_date = "2026-06-02"
                self.status = MeetStatus.scheduled
                self.medal_gold_min = None
                self.medal_silver_min = None

        meet = MeetRead.model_validate(ORMObject())

        assert meet.id == 1
        assert meet.district_id == 7
        assert meet.name == "District Meet"
