"""Pydantic validation tests for the JudgeCreate/JudgeUpdate/JudgeRead schemas."""

import pytest
from pydantic import ValidationError

from app.models import JudgeCategory
from app.schemas.judge import JudgeCreate, JudgeRead, JudgeUpdate


class TestJudgeCreate:
    def test_create_judge_valid(self):
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "country_code": "USA",
            "category": "category_1",
        }
        judge = JudgeCreate.model_validate(data)
        assert judge.first_name == "John"
        assert judge.last_name == "Doe"
        assert judge.country_code == "USA"
        assert judge.category == JudgeCategory.category_1

    def test_invalid_country_code(self):
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "country_code": "US",  # Invalid country code
            "category": "category_1",
        }
        with pytest.raises(ValidationError):
            JudgeCreate.model_validate(data)

    def test_creat_judge_country_code_numeric(self):
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "country_code": "123",  # Invalid country code
            "category": "category_1",
        }
        with pytest.raises(ValidationError):
            JudgeCreate.model_validate(data)

    def test_create_judge_country_code_with_whitespace(self):
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "country_code": " usa ",  # Valid country code with whitespace
            "category": "category_1",
        }
        judge = JudgeCreate.model_validate(data)
        assert judge.country_code == "USA"  # Should be stripped and uppercased

    def test_create_judge_country_code_none(self):
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "country_code": None,  # Valid case with None
            "category": "category_1",
        }
        judge = JudgeCreate.model_validate(data)
        assert judge.country_code is None

    def test_create_judge_country_code_empty_string(self):
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "country_code": "",  # Invalid case with empty string
            "category": "category_1",
        }
        with pytest.raises(ValidationError):
            JudgeCreate.model_validate(data)

    def test_create_judge_names_with_whitespace(self):
        data = {
            "first_name": "  John  ",
            "last_name": "  Doe  ",
            "country_code": "USA",
            "category": "category_1",
        }
        judge = JudgeCreate.model_validate(data)
        assert judge.first_name == "John"  # Should be stripped
        assert judge.last_name == "Doe"  # Should be stripped

    def test_create_judge_missing_first_name(self):
        data = {"last_name": "Doe", "country_code": "USA", "category": "category_1"}
        with pytest.raises(ValidationError):
            JudgeCreate.model_validate(data)

    def test_create_judge_missing_last_name(self):
        data = {"first_name": "John", "country_code": "USA", "category": "category_1"}
        with pytest.raises(ValidationError):
            JudgeCreate.model_validate(data)

    def test_create_judge_country_code_and_category_omitted(self):
        # country_code/category aren't in the payload at all (not even as None) --
        # distinct from test_create_judge_country_code_none, which sends the key explicitly.
        data = {"first_name": "John", "last_name": "Doe"}
        judge = JudgeCreate.model_validate(data)
        assert judge.country_code is None
        assert judge.category is None

    def test_create_judge_country_code_non_string_type_rejected(self):
        # Regression guard: validate_country_code's isinstance(v, str) branch must not
        # silently swallow a non-string input into None -- it should fail validation instead.
        data = {"first_name": "John", "last_name": "Doe", "country_code": 123}
        with pytest.raises(ValidationError):
            JudgeCreate.model_validate(data)


class TestJudgeUpdate:
    def test_update_judge_valid(self):
        data = {
            "first_name": "Jane",
            "last_name": "Smith",
            "country_code": "CAN",
            "category": "category_2",
        }
        judge = JudgeUpdate.model_validate(data)
        assert judge.first_name == "Jane"
        assert judge.last_name == "Smith"
        assert judge.country_code == "CAN"
        assert judge.category == JudgeCategory.category_2

    def test_update_judge_country_code_none(self):
        data = {
            "first_name": "Jane",
            "last_name": "Smith",
            "country_code": None,  # Valid case with None
            "category": "category_2",
        }
        judge = JudgeUpdate.model_validate(data)
        assert judge.country_code is None

    def test_update_judge_country_code_invalid(self):
        data = {
            "first_name": "Jane",
            "last_name": "Smith",
            "country_code": "C",  # Invalid country code
            "category": "category_2",
        }
        with pytest.raises(ValidationError):
            JudgeUpdate.model_validate(data)

    def test_update_judge_names_with_whitespace(self):
        data = {
            "first_name": "  Jane  ",
            "last_name": "  Smith  ",
            "country_code": "CAN",
            "category": "category_2",
        }
        judge = JudgeUpdate.model_validate(data)
        assert judge.first_name == "Jane"  # Should be stripped
        assert judge.last_name == "Smith"  # Should be stripped

    def test_update_judge_country_code_with_whitespace(self):
        data = {
            "first_name": "Jane",
            "last_name": "Smith",
            "country_code": " can ",  # Valid country code with whitespace
            "category": "category_2",
        }
        judge = JudgeUpdate.model_validate(data)
        assert judge.country_code == "CAN"  # Should be stripped and uppercased

    def test_update_judge_country_code_empty_string(self):
        data = {
            "country_code": "",  # Invalid case with empty string
        }
        with pytest.raises(ValidationError):
            JudgeUpdate.model_validate(data)

    def test_update_judge_first_name_only(self):
        data = {"first_name": "Alice"}
        judge = JudgeUpdate.model_validate(data)
        assert judge.first_name == "Alice"
        assert judge.last_name is None
        assert judge.country_code is None
        assert judge.category is None

    def test_update_judge_last_name_only(self):
        data = {"last_name": "Johnson"}
        judge = JudgeUpdate.model_validate(data)
        assert judge.first_name is None
        assert judge.last_name == "Johnson"
        assert judge.country_code is None
        assert judge.category is None

    def test_update_judge_country_code_only(self):
        data = {"country_code": "GBR"}
        judge = JudgeUpdate.model_validate(data)
        assert judge.first_name is None
        assert judge.last_name is None
        assert judge.country_code == "GBR"
        assert judge.category is None

    def test_update_judge_category_only(self):
        data = {"category": "category_3"}
        judge = JudgeUpdate.model_validate(data)
        assert judge.first_name is None
        assert judge.last_name is None
        assert judge.country_code is None
        assert judge.category == JudgeCategory.category_3

    def test_update_judge_all_fields_none(self):
        data = {}
        judge = JudgeUpdate.model_validate(data)
        assert judge.first_name is None
        assert judge.last_name is None
        assert judge.country_code is None
        assert judge.category is None

    def test_update_judge_country_code_numeric_invalid(self):
        data = {"country_code": "123"}
        with pytest.raises(ValidationError):
            JudgeUpdate.model_validate(data)

    def test_update_judge_exclude_unset_only_includes_provided_fields(self):
        # The router builds updates via payload.model_dump(exclude_unset=True) -- this is
        # the actual contract the JudgeUpdate router handler will depend on, so it's worth
        # testing directly rather than just the individual field values.
        judge = JudgeUpdate.model_validate({"category": "category_3"})
        assert judge.model_dump(exclude_unset=True) == {"category": "category_3"}


class TestJudgeRead:
    def test_read_judge(self):
        data = {
            "id": 1,
            "first_name": "John",
            "last_name": "Doe",
            "country_code": "USA",
            "category": "category_1",
        }
        judge = JudgeRead.model_validate(data)
        assert judge.id == 1
        assert judge.first_name == "John"
        assert judge.last_name == "Doe"
        assert judge.country_code == "USA"
        assert judge.category == JudgeCategory.category_1

    def test_read_judge_optional_fields_none(self):
        data = {
            "id": 2,
            "first_name": "Jane",
            "last_name": "Smith",
            "country_code": None,
            "category": None,
        }
        judge = JudgeRead.model_validate(data)
        assert judge.id == 2
        assert judge.first_name == "Jane"
        assert judge.last_name == "Smith"
        assert judge.country_code is None
        assert judge.category is None

    def test_read_judge_from_orm_like_object(self):
        class JudgeORM:
            def __init__(self, id, first_name, last_name, country_code, category):
                self.id = id
                self.first_name = first_name
                self.last_name = last_name
                self.country_code = country_code
                self.category = category

        orm_judge = JudgeORM(3, "Alice", "Johnson", "CAN", JudgeCategory.category_2)
        judge = JudgeRead.model_validate(orm_judge)
        assert judge.id == 3
        assert judge.first_name == "Alice"
        assert judge.last_name == "Johnson"
        assert judge.country_code == "CAN"
        assert judge.category == JudgeCategory.category_2

    def test_judge_read_missing_required_field(self):
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "country_code": "USA",
            "category": "category_1",
        }
        with pytest.raises(ValidationError):
            JudgeRead.model_validate(data)
