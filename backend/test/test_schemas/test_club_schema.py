import pytest
from pydantic import ValidationError

from app.schemas.club import ClubCreate, ClubRead, ClubUpdate


##-- Create
class TestClubCreateSchema:
    def test_club_create_valid(self):
        data = {
            "name": "Van Der Stel",
            "district_id": 1,
            "abbreviation": "VDS",
        }
        club_create = ClubCreate(**data)
        assert club_create.name == "Van Der Stel"
        assert club_create.district_id == 1
        assert club_create.abbreviation == "VDS"

    def test_club_create_strip_whitespace(self):
        data = {
            "name": "  Van Der Stel  ",
            "district_id": 1,
            "abbreviation": "  VDS  ",
        }
        club_create = ClubCreate(**data)
        assert club_create.name == "Van Der Stel"
        assert club_create.abbreviation == "VDS"

    def test_club_create_invalid_name_too_short(self):
        data = {
            "name": "V",
            "district_id": 1,
            "abbreviation": "VDS",
        }
        with pytest.raises(ValidationError):
            ClubCreate.model_validate(data)

    def test_club_create_invalid_abbreviation_too_long(self):
        data = {
            "name": "Van Der Stel",
            "district_id": 1,
            "abbreviation": "VDSVDSVDSVDS",
        }
        with pytest.raises(ValidationError):
            ClubCreate.model_validate(data)

    def test_club_create_invalid_district_id_negative(self):
        data = {
            "name": "Van Der Stel",
            "district_id": -1,
            "abbreviation": "VDS",
        }
        with pytest.raises(ValidationError):
            ClubCreate.model_validate(data)

    def test_club_create_invalid_district_id_zero(self):
        data = {
            "name": "Van Der Stel",
            "district_id": 0,
            "abbreviation": "VDS",
        }
        with pytest.raises(ValidationError):
            ClubCreate.model_validate(data)

    def test_club_create_invalid_district_id_missing(self):
        data = {
            "name": "Van Der Stel",
            "abbreviation": "VDS",
        }
        with pytest.raises(ValidationError):
            ClubCreate.model_validate(data)

    def test_club_create_invalid_name_missing(self):
        data = {
            "district_id": 1,
            "abbreviation": "VDS",
        }
        with pytest.raises(ValidationError):
            ClubCreate.model_validate(data)

    def test_club_create_invalid_abbreviation_missing(self):
        data = {
            "name": "Van Der Stel",
            "district_id": 1,
        }
        with pytest.raises(ValidationError):
            ClubCreate.model_validate(data)

    def test_club_create_invalid_name_too_long(self):
        data = {
            "name": "V" * 256,
            "district_id": 1,
            "abbreviation": "VDS",
        }
        with pytest.raises(ValidationError):
            ClubCreate.model_validate(data)


class TestClubUpdateSchema:
    def test_club_update_valid(self):
        data = {
            "name": "Van Der Stel Updated",
            "abbreviation": "VDSU",
        }
        club_update = ClubUpdate(**data)
        assert club_update.name == "Van Der Stel Updated"
        assert club_update.abbreviation == "VDSU"

    def test_club_update_strip_whitespace(self):
        data = {
            "name": "  Van Der Stel Updated  ",
            "abbreviation": "  VDSU  ",
        }
        club_update = ClubUpdate(**data)
        assert club_update.name == "Van Der Stel Updated"
        assert club_update.abbreviation == "VDSU"

    def test_club_update_invalid_name_too_short(self):
        data = {
            "name": "V",
            "abbreviation": "VDSU",
        }
        with pytest.raises(ValidationError):
            ClubUpdate.model_validate(data)

    def test_club_update_invalid_abbreviation_too_long(self):
        data = {
            "name": "Van Der Stel Updated",
            "abbreviation": "VDSUVDSUVDSU",
        }
        with pytest.raises(ValidationError):
            ClubUpdate.model_validate(data)

    def test_club_update_invalid_name_too_long(self):
        data = {
            "name": "V" * 256,
            "abbreviation": "VDSU",
        }
        with pytest.raises(ValidationError):
            ClubUpdate.model_validate(data)

    def test_club_update_all_optional(self):
        data = {}
        club_update = ClubUpdate(**data)
        assert club_update.name is None
        assert club_update.abbreviation is None

    def test_club_update_district_id_excluded(self):
        data = {
            "name": "Van Der Stel Updated",
            "abbreviation": "VDSU",
            "district_id": 2,  # This should be ignored
        }
        club_update = ClubUpdate(**data)
        assert club_update.name == "Van Der Stel Updated"
        assert club_update.abbreviation == "VDSU"
        assert not hasattr(club_update, "district_id")  # district_id should not be present


class TestClubReadSchema:
    def test_club_read_schema_valid(self):
        data = {
            "id": 1,
            "name": "Van Der Stel",
            "district_id": 1,
            "abbreviation": "VDS",
        }
        club_read = ClubRead.model_validate(data)
        assert club_read.id == 1
        assert club_read.name == "Van Der Stel"
        assert club_read.district_id == 1
        assert club_read.abbreviation == "VDS"

    def test_club_read_schema_invalid_missing_fields(self):
        data = {
            "id": 1,
            "name": "Van Der Stel",
            # district_id is missing
            "abbreviation": "VDS",
        }
        with pytest.raises(ValidationError):
            ClubRead.model_validate(data)

    def test_club_read_make_from_orm_object(self):
        class DummyORM:
            def __init__(self, id, name, district_id, abbreviation):
                self.id = id
                self.name = name
                self.district_id = district_id
                self.abbreviation = abbreviation

        orm_obj = DummyORM(id=1, name="Van Der Stel", district_id=1, abbreviation="VDS")
        club_read = ClubRead.model_validate(orm_obj)
        assert club_read.id == 1
        assert club_read.name == "Van Der Stel"
        assert club_read.district_id == 1
        assert club_read.abbreviation == "VDS"

    def test_club_read_missing_id_raises_validation_error(self):
        data = {
            "name": "Van Der Stel",
            "district_id": 1,
            "abbreviation": "VDS",
        }
        with pytest.raises(ValidationError):
            ClubRead.model_validate(data)

    def test_club_read_missing_district_id_raises_validation_error(self):
        data = {
            "id": 1,
            "name": "Van Der Stel",
            "abbreviation": "VDS",
        }
        with pytest.raises(ValidationError):
            ClubRead.model_validate(data)
