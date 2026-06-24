from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.gymnast import GymnastCreate, GymnastRead, GymnastUpdate


class TestGymnastCreateSchema:
    def test_gymnast_create_schema_valid(self):
        data = {
            "club_id": 1,
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "2000-01-01",
            "country_code": "USA",
        }
        gymnast_create = GymnastCreate(**data)
        assert gymnast_create.club_id == 1
        assert gymnast_create.first_name == "John"
        assert gymnast_create.last_name == "Doe"
        assert gymnast_create.date_of_birth == date(2000, 1, 1)
        assert gymnast_create.country_code == "USA"

    def test_gymnast_create_schema_strip_whitespace(self):
        data = {
            "club_id": 1,
            "first_name": "  John  ",
            "last_name": "  Doe  ",
            "date_of_birth": "2000-01-01",
            "country_code": "  USA  ",
        }
        gymnast_create = GymnastCreate(**data)
        assert gymnast_create.first_name == "John"
        assert gymnast_create.last_name == "Doe"
        assert gymnast_create.country_code == "USA"

    def test_gymnast_create_schema_invalid_country_code(self):
        data = {
            "club_id": 1,
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "2000-01-01",
            "country_code": "US",
        }
        with pytest.raises(ValidationError):
            GymnastCreate.model_validate(data)

    def test_gymnast_create_minimal_valid_data(self):
        data = {
            "first_name": "John",
            "last_name": "Doe",
        }
        gymnast_create = GymnastCreate.model_validate(data)

        assert gymnast_create.club_id is None
        assert gymnast_create.first_name == "John"
        assert gymnast_create.last_name == "Doe"
        assert gymnast_create.date_of_birth is None
        assert gymnast_create.country_code is None

    def test_gymnast_create_country_code_uppercase(self):
        data = {
            "club_id": 1,
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "2000-01-01",
            "country_code": "usa",
        }
        gymnast_create = GymnastCreate.model_validate(data)
        assert gymnast_create.country_code == "USA"

    def test_gymnast_create_schema_invalid_date_of_birth(self):
        data = {
            "club_id": 1,
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "2000-13-01",  # Invalid month
            "country_code": "USA",
        }
        with pytest.raises(ValidationError):
            GymnastCreate.model_validate(data)

    def test_gymnast_create_schema_invalid_date_of_birth_format(self):
        data = {
            "club_id": 1,
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "01-01-2000",  # Invalid format
            "country_code": "USA",
        }
        with pytest.raises(ValidationError):
            GymnastCreate.model_validate(data)

    def test_gymnast_create_strip_whitespace_in_names(self):
        data = {
            "first_name": "  John  ",
            "last_name": "  Doe  ",
        }
        gymnast_create = GymnastCreate.model_validate(data)
        assert gymnast_create.first_name == "John"
        assert gymnast_create.last_name == "Doe"

    def test_gymnast_create_schema_invalid_club_id(self):
        data = {
            "club_id": -1,  # Invalid club_id
            "first_name": "John",
            "last_name": "Doe",
        }
        with pytest.raises(ValidationError):
            GymnastCreate.model_validate(data)

    def test_gymnast_create_schema_invalid_first_name(self):
        data = {
            "first_name": "",  # Invalid first_name
            "last_name": "Doe",
        }
        with pytest.raises(ValidationError):
            GymnastCreate.model_validate(data)

    def test_gymnast_create_country_code_too_long(self):
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "country_code": "USAA",  # Too long
        }
        with pytest.raises(ValidationError):
            GymnastCreate.model_validate(data)

    def test_gymnast_create_country_code_too_short(self):
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "country_code": "US",  # Too short
        }
        with pytest.raises(ValidationError):
            GymnastCreate.model_validate(data)

    def test_gymnast_create_country_code_non_alpha(self):
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "country_code": "U1A",  # Contains a digit
        }
        with pytest.raises(ValidationError):
            GymnastCreate.model_validate(data)


class TestGymnastUpdateSchema:
    def test_gymnast_update_schema_valid(self):
        data = {
            "club_id": 1,
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "2000-01-01",
            "country_code": "USA",
        }
        gymnast_update = GymnastUpdate.model_validate(data)
        assert gymnast_update.club_id == 1
        assert gymnast_update.first_name == "John"
        assert gymnast_update.last_name == "Doe"
        assert gymnast_update.date_of_birth == date(2000, 1, 1)
        assert gymnast_update.country_code == "USA"

    def test_gymnast_update_schema_strip_whitespace(self):
        data = {
            "club_id": 1,
            "first_name": "  John  ",
            "last_name": "  Doe  ",
            "date_of_birth": "2000-01-01",
            "country_code": "  USA  ",
        }
        gymnast_update = GymnastUpdate.model_validate(data)
        assert gymnast_update.first_name == "John"
        assert gymnast_update.last_name == "Doe"
        assert gymnast_update.country_code == "USA"

    def test_gymnast_all_optional_fields(self):
        data = {}
        gymnast_update = GymnastUpdate.model_validate(data)
        assert gymnast_update.club_id is None
        assert gymnast_update.first_name is None
        assert gymnast_update.last_name is None
        assert gymnast_update.date_of_birth is None
        assert gymnast_update.country_code is None

    def test_gymnast_update_club_id_invalid(self):
        data = {
            "club_id": -1,  # Invalid club_id
        }
        with pytest.raises(ValidationError):
            GymnastUpdate.model_validate(data)

    def test_gymnast_update_country_code_invalid(self):
        data = {
            "country_code": "US",  # Invalid country_code
        }
        with pytest.raises(ValidationError):
            GymnastUpdate.model_validate(data)

    def test_gymnast_update_can_set_club_id_to_none(self):
        data = {
            "club_id": None,  # Setting club_id to None
        }
        gymnast_update = GymnastUpdate.model_validate(data)
        assert gymnast_update.club_id is None

    def test_gymnast_update_partial_update(self):
        data = {
            "first_name": "John",
        }
        gymnast_update = GymnastUpdate.model_validate(data)
        assert gymnast_update.first_name == "John"
        assert gymnast_update.last_name is None
        assert gymnast_update.club_id is None
        assert gymnast_update.date_of_birth is None
        assert gymnast_update.country_code is None

    def test_gymnast_update_country_code_uppercase(self):
        data = {
            "country_code": "usa",  # Lowercase input
        }
        gymnast_update = GymnastUpdate.model_validate(data)
        assert gymnast_update.country_code == "USA"  # Should be converted to uppercase

    def test_gymnast_update_invalid_date_of_birth(self):
        data = {
            "date_of_birth": "2000-13-01",  # Invalid month
        }
        with pytest.raises(ValidationError):
            GymnastUpdate.model_validate(data)

    def test_gymnast_update_invalid_date_of_birth_format(self):
        data = {
            "date_of_birth": "01-01-2000",  # Invalid format
        }
        with pytest.raises(ValidationError):
            GymnastUpdate.model_validate(data)

    def test_gymnast_update_strip_whitespace_in_names(self):
        data = {
            "first_name": "  John  ",
            "last_name": "  Doe  ",
        }
        gymnast_update = GymnastUpdate.model_validate(data)
        assert gymnast_update.first_name == "John"
        assert gymnast_update.last_name == "Doe"

    def test_gymnast_update_country_code_too_long(self):
        data = {
            "country_code": "USAA",  # Too long
        }
        with pytest.raises(ValidationError):
            GymnastUpdate.model_validate(data)

    def test_gymnast_update_country_code_too_short(self):
        data = {
            "country_code": "US",  # Too short
        }
        with pytest.raises(ValidationError):
            GymnastUpdate.model_validate(data)

    def test_gymnast_update_country_code_non_alpha(self):
        data = {
            "country_code": "U1A",  # Contains a digit
        }
        with pytest.raises(ValidationError):
            GymnastUpdate.model_validate(data)


class TestGymnastReadSchema:
    def test_gymnast_read_schema_valid(self):
        data = {
            "id": 1,
            "club_id": 1,
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": date(2000, 1, 1),
            "country_code": "USA",
        }
        gymnast_read = GymnastRead.model_validate(data)
        assert gymnast_read.id == 1
        assert gymnast_read.club_id == 1
        assert gymnast_read.first_name == "John"
        assert gymnast_read.last_name == "Doe"
        assert gymnast_read.date_of_birth == date(2000, 1, 1)
        assert gymnast_read.country_code == "USA"

    def test_gymnast_read_from_orm_like_object(self):
        class ORMObject:
            def __init__(self, id, club_id, first_name, last_name, date_of_birth, country_code):
                self.id = id
                self.club_id = club_id
                self.first_name = first_name
                self.last_name = last_name
                self.date_of_birth = date_of_birth
                self.country_code = country_code

        orm_obj = ORMObject(
            id=1,
            club_id=1,
            first_name="John",
            last_name="Doe",
            date_of_birth=date(2000, 1, 1),
            country_code="USA",
        )
        gymnast_read = GymnastRead.model_validate(orm_obj)
        assert gymnast_read.id == 1
        assert gymnast_read.club_id == 1
        assert gymnast_read.first_name == "John"
        assert gymnast_read.last_name == "Doe"
        assert gymnast_read.date_of_birth == date(2000, 1, 1)
        assert gymnast_read.country_code == "USA"

    def test_gymnast_read_missing_fields(self):
        data = {
            "id": 1,
            "club_id": 1,
            "first_name": "John",
            # last_name is missing
            "date_of_birth": date(2000, 1, 1),
            "country_code": "USA",
        }
        with pytest.raises(ValidationError):
            GymnastRead.model_validate(data)

    def test_gymnast_read_nullable_fields(self):
        data = {
            "id": 1,
            "club_id": None,
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": None,
            "country_code": None,
        }
        gymnast_read = GymnastRead.model_validate(data)
        assert gymnast_read.id == 1
        assert gymnast_read.club_id is None
        assert gymnast_read.first_name == "John"
        assert gymnast_read.last_name == "Doe"
        assert gymnast_read.date_of_birth is None
        assert gymnast_read.country_code is None

    def test_gymnast_read_missing_id(self):
        data = {
            "club_id": 1,
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": date(2000, 1, 1),
            "country_code": "USA",
        }
        with pytest.raises(ValidationError):
            GymnastRead.model_validate(data)
