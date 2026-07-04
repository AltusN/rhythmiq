import pytest
from pydantic import ValidationError

from app.models import AgeGroup, Level
from app.schemas.meet_entry import MeetEntryCreate, MeetEntryRead, MeetEntryUpdate


class TestMeetEntryCreate:
    def test_meet_entry_create_valid_all_fields(self):
        data = {
            "meet_id": 1,
            "gymnast_id": 1,
            "level": Level.junior,
            "age_group": AgeGroup.under_8,
            "bib_number": "123",
            "entry_fee_paid": True,
        }
        entry = MeetEntryCreate(**data)

        assert entry.meet_id == 1
        assert entry.gymnast_id == 1
        assert entry.level == Level.junior
        assert entry.age_group == AgeGroup.under_8
        assert entry.bib_number == "123"
        assert entry.entry_fee_paid is True

    def test_meet_entry_create_minimal_valid_fields(self):
        data = {
            "meet_id": 1,
            "gymnast_id": 1,
            "level": Level.junior,
            "age_group": AgeGroup.under_8,
            "bib_number": "123",
        }
        entry = MeetEntryCreate.model_validate(data)

        assert entry.meet_id == 1
        assert entry.gymnast_id == 1
        assert entry.level == Level.junior
        assert entry.age_group == AgeGroup.under_8
        assert entry.bib_number == "123"
        assert entry.entry_fee_paid is False

    def test_meet_entry_create_bib_number_required(self):
        data = {
            "meet_id": 1,
            "gymnast_id": 1,
            "level": Level.junior,
            "age_group": AgeGroup.under_8,
        }
        with pytest.raises(ValidationError):
            MeetEntryCreate.model_validate(data)

    def test_invalid_meet_entry_create_missing_fields(self):
        data = {
            "meet_id": 1,
            "gymnast_id": 1,
            # Missing level and age_group
            "bib_number": "123",
            "entry_fee_paid": True,
        }
        with pytest.raises(ValidationError):
            MeetEntryCreate(**data)

    def test_meet_entry_create_bib_number_with_leading_zeros(self):
        data = {
            "meet_id": 1,
            "gymnast_id": 1,
            "level": Level.junior,
            "age_group": AgeGroup.under_8,
            "bib_number": "00123",
            "entry_fee_paid": True,
        }
        entry = MeetEntryCreate(**data)

        assert entry.bib_number == "00123"

    def test_meet_entry_meet_id_required(self):
        data = {
            "gymnast_id": 1,
            "level": Level.junior,
            "age_group": AgeGroup.under_8,
        }
        with pytest.raises(ValidationError):
            MeetEntryCreate(**data)

    def test_meet_entry_gymnast_or_group_id_required(self):
        data = {
            "meet_id": 1,
            "level": Level.junior,
            "age_group": AgeGroup.under_8,
        }
        with pytest.raises(ValidationError):
            MeetEntryCreate(**data)

    def test_meet_entry_create_with_group_id(self):
        data = {
            "meet_id": 1,
            "group_id": 1,
            "level": Level.junior,
            "age_group": AgeGroup.under_8,
            "bib_number": "123",
        }
        entry = MeetEntryCreate(**data)

        assert entry.meet_id == 1
        assert entry.gymnast_id is None
        assert entry.group_id == 1

    def test_meet_entry_create_both_gymnast_and_group_id_fails(self):
        data = {
            "meet_id": 1,
            "gymnast_id": 1,
            "group_id": 1,
            "level": Level.junior,
            "age_group": AgeGroup.under_8,
        }
        with pytest.raises(ValidationError):
            MeetEntryCreate(**data)

    def test_meet_entry_level_required(self):
        data = {
            "meet_id": 1,
            "gymnast_id": 1,
            "age_group": AgeGroup.under_8,
        }
        with pytest.raises(ValidationError):
            MeetEntryCreate(**data)

    def test_meet_entry_invalid_level(self):
        data = {
            "meet_id": 1,
            "gymnast_id": 1,
            "level": "invalid_level",
            "age_group": AgeGroup.under_8,
        }
        with pytest.raises(ValidationError):
            MeetEntryCreate(**data)

    def test_meet_entry_age_group_invalid(self):
        data = {
            "meet_id": 1,
            "gymnast_id": 1,
            "level": Level.junior,
            "age_group": "invalid_age_group",
        }
        with pytest.raises(ValidationError):
            MeetEntryCreate(**data)

    def test_meet_entry_level_from_string(self):
        data = {
            "meet_id": 1,
            "gymnast_id": 1,
            "level": "junior",
            "age_group": AgeGroup.under_8,
            "bib_number": "123",
        }
        entry = MeetEntryCreate(**data)

        assert entry.level == Level.junior


class TestMeetEntryUpdate:
    def test_meet_entry_update_valid(self):
        data = {
            "level": Level.senior,
            "age_group": AgeGroup.under_10,
            "bib_number": "456",
            "entry_fee_paid": True,
        }
        entry_update = MeetEntryUpdate(**data)

        assert entry_update.level == Level.senior
        assert entry_update.age_group == AgeGroup.under_10
        assert entry_update.bib_number == "456"
        assert entry_update.entry_fee_paid is True

    def test_meet_entry_update_partial(self):
        data = {
            "level": Level.senior,
        }
        entry_update = MeetEntryUpdate.model_validate(data)

        assert entry_update.level == Level.senior
        assert entry_update.age_group is None
        assert entry_update.bib_number is None
        assert entry_update.entry_fee_paid is None

    def test_meet_entry_update_invalid_level(self):
        data = {
            "level": "invalid_level",
        }
        with pytest.raises(ValidationError):
            MeetEntryUpdate.model_validate(data)

    def test_meet_entry_update_invalid_age_group(self):
        data = {
            "age_group": "invalid_age_group",
        }
        with pytest.raises(ValidationError):
            MeetEntryUpdate.model_validate(data)

    def test_meet_entry_update_no_meet_id_or_gymnast_id(self):
        # gymnast_id and meet_id are not updatable, so they should not be present in the update schema. This test ensures that if they are provided, they are ignored or raise an error.

        assert "gymnast_id" not in MeetEntryUpdate.model_fields
        assert "meet_id" not in MeetEntryUpdate.model_fields

    def test_meet_entry_update_partial_level_only(self):
        data = {
            "level": Level.senior,
        }
        entry_update = MeetEntryUpdate.model_validate(data)

        assert entry_update.level == Level.senior
        assert entry_update.age_group is None
        assert entry_update.bib_number is None
        assert entry_update.entry_fee_paid is None

    def test_meet_entry_update_partial_age_group_only(self):
        data = {
            "age_group": AgeGroup.under_10,
        }
        entry_update = MeetEntryUpdate.model_validate(data)

        assert entry_update.level is None
        assert entry_update.age_group == AgeGroup.under_10
        assert entry_update.bib_number is None
        assert entry_update.entry_fee_paid is None

    def test_meet_entry_update_partial_entry_fee_paid_only(self):
        data = {
            "entry_fee_paid": True,
        }
        entry_update = MeetEntryUpdate.model_validate(data)

        assert entry_update.level is None
        assert entry_update.age_group is None
        assert entry_update.bib_number is None
        assert entry_update.entry_fee_paid is True

    def test_meet_entry_update_partial_bib_number_only(self):
        data = {
            "bib_number": "789",
        }
        entry_update = MeetEntryUpdate.model_validate(data)

        assert entry_update.level is None
        assert entry_update.age_group is None
        assert entry_update.bib_number == "789"
        assert entry_update.entry_fee_paid is None


class TestMeetEntryRead:
    def test_meet_entry_read_from_dict(self):
        data = {
            "id": 1,
            "meet_id": 1,
            "gymnast_id": 1,
            "level": Level.junior,
            "age_group": AgeGroup.under_8,
            "bib_number": "123",
            "entry_fee_paid": True,
        }
        entry_read = MeetEntryRead.model_validate(data)

        assert entry_read.id == 1
        assert entry_read.meet_id == 1
        assert entry_read.gymnast_id == 1
        assert entry_read.level == Level.junior
        assert entry_read.age_group == AgeGroup.under_8
        assert entry_read.bib_number == "123"
        assert entry_read.entry_fee_paid is True

    def test_meet_entry_read_valid(self):
        data = {
            "id": 1,
            "meet_id": 1,
            "gymnast_id": 1,
            "level": Level.junior,
            "age_group": AgeGroup.under_8,
            "bib_number": "123",
            "entry_fee_paid": True,
        }
        entry_read = MeetEntryRead.model_validate(data)

        assert entry_read.id == 1
        assert entry_read.meet_id == 1
        assert entry_read.gymnast_id == 1
        assert entry_read.level == Level.junior
        assert entry_read.age_group == AgeGroup.under_8
        assert entry_read.bib_number == "123"
        assert entry_read.entry_fee_paid is True

    def test_meet_entry_read_missing_fields(self):
        data = {
            "id": 1,
            "meet_id": 1,
            # Missing level, age_group, bib_number, entry_fee_paid
        }
        with pytest.raises(ValidationError):
            MeetEntryRead.model_validate(data)

    def test_meet_entry_read_group_entry(self):
        data = {
            "id": 1,
            "meet_id": 1,
            "group_id": 1,
            "level": Level.junior,
            "age_group": AgeGroup.under_8,
            "bib_number": "123",
            "entry_fee_paid": True,
        }
        entry_read = MeetEntryRead.model_validate(data)

        assert entry_read.gymnast_id is None
        assert entry_read.group_id == 1

    def test_meet_entry_read_level_serialization(self):
        data = {
            "id": 1,
            "meet_id": 1,
            "gymnast_id": 1,
            "level": Level.junior,
            "age_group": AgeGroup.under_8,
            "bib_number": "123",
            "entry_fee_paid": True,
        }
        entry_read = MeetEntryRead.model_validate(data)

        assert entry_read.level == "junior"

    def test_meet_entry_read_from_orm_object(self):
        class DummyORM:
            def __init__(
                self, id, meet_id, gymnast_id, group_id, level, age_group, bib_number, entry_fee_paid
            ):
                self.id = id
                self.meet_id = meet_id
                self.gymnast_id = gymnast_id
                self.group_id = group_id
                self.level = level
                self.age_group = age_group
                self.bib_number = bib_number
                self.entry_fee_paid = entry_fee_paid

        orm_obj = DummyORM(
            id=1,
            meet_id=1,
            gymnast_id=1,
            group_id=None,
            level=Level.junior,
            age_group=AgeGroup.under_8,
            bib_number="123",
            entry_fee_paid=True,
        )
        entry_read = MeetEntryRead.model_validate(orm_obj)

        assert entry_read.id == 1
        assert entry_read.meet_id == 1
        assert entry_read.gymnast_id == 1
        assert entry_read.level == Level.junior
        assert entry_read.age_group == "u8"
        assert entry_read.bib_number == "123"
        assert entry_read.entry_fee_paid is True

    def test_meet_entry_read_missing_id_raises_validation_error(self):
        data = {
            "meet_id": 1,
            "gymnast_id": 1,
            "level": Level.junior,
            "age_group": AgeGroup.under_8,
            "bib_number": "123",
            "entry_fee_paid": True,
        }
        with pytest.raises(ValidationError):
            MeetEntryRead.model_validate(data)
