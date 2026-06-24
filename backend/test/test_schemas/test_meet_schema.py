
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
        meet = MeetCreate.model_validate(
            {
                "district_id": None,
                "name": "Invalid Meet",
                "location": "Main Arena",
                "start_date": "2026-06-01",
                "end_date": "2026-06-02",
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

        meet = MeetRead.model_validate(ORMObject())

        assert meet.id == 1
        assert meet.district_id == 7
        assert meet.name == "District Meet"
