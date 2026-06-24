import pytest
from pydantic import ValidationError

from app.schemas.coach import CoachCreate, CoachRead, CoachUpdate


class TestCoachCreate:
    def test_valid_minimal(self):
        c = CoachCreate(first_name="Annette", last_name="Nel", club_id=1)
        assert c.first_name == "Annette"
        assert c.last_name == "Nel"
        assert c.club_id == 1
        assert c.is_head_coach is False

    def test_valid_with_head_coach(self):
        c = CoachCreate(first_name="Annette", last_name="Nel", club_id=1, is_head_coach=True)
        assert c.is_head_coach is True

    def test_strip_whitespace(self):
        c = CoachCreate(
            first_name="  Annette  ", last_name="  Nel  ", club_id=1, is_head_coach=True
        )
        assert c.first_name == "Annette"
        assert c.last_name == "Nel"

    def test_club_id_must_be_positive(self):
        with pytest.raises(ValidationError):
            CoachCreate(first_name="Annette", last_name="Nel", club_id=0)

    def test_club_id_required(self):
        with pytest.raises(ValidationError):
            CoachCreate.model_validate({"first_name": "Annette", "last_name": "Nel"})

    def test_first_name_required(self):
        with pytest.raises(ValidationError):
            CoachCreate.model_validate({"last_name": "Nel", "club_id": 1})

    def test_last_name_required(self):
        with pytest.raises(ValidationError):
            CoachCreate.model_validate({"first_name": "Annette", "club_id": 1})

    def test_first_name_too_short(self):
        with pytest.raises(ValidationError):
            CoachCreate.model_validate({"first_name": "A", "last_name": "Nel", "club_id": 1})

    def test_last_name_too_short(self):
        with pytest.raises(ValidationError):
            CoachCreate.model_validate({"first_name": "Annette", "last_name": "N", "club_id": 1})

    def test_club_id_must_be_int(self):
        with pytest.raises(ValidationError):
            CoachCreate.model_validate(
                {"first_name": "Annette", "last_name": "Nel", "club_id": "one"}
            )

    def test_strip_whitespace_first_name_too_short_after_strip(self):
        with pytest.raises(ValidationError):
            CoachCreate.model_validate({"first_name": "  A  ", "last_name": "Nel", "club_id": 1})


class CoachUpdateTests:
    def test_all_optional(self):
        c = CoachUpdate.model_validate({})
        assert c.first_name is None
        assert c.last_name is None
        assert c.is_head_coach is None

    def test_partial_first_name_only(self):
        c = CoachUpdate.model_validate({"first_name": "Annette"})
        assert c.first_name == "Annette"
        assert c.last_name is None
        assert c.is_head_coach is None

    def test_partial_last_name_only(self):
        c = CoachUpdate.model_validate({"last_name": "Nel"})
        assert c.first_name is None
        assert c.last_name == "Nel"
        assert c.is_head_coach is None

    def test_partial_is_head_coach_only(self):
        c = CoachUpdate.model_validate({"is_head_coach": True})
        assert c.first_name is None
        assert c.last_name is None
        assert c.is_head_coach is True

    def test_strip_whitespace(self):
        c = CoachUpdate.model_validate(
            {"first_name": "  Annette  ", "last_name": "  Nel  ", "is_head_coach": True}
        )
        assert c.first_name == "Annette"
        assert c.last_name == "Nel"
        assert c.is_head_coach is True

    def test_first_name_too_short(self):
        with pytest.raises(ValidationError):
            CoachUpdate.model_validate({"first_name": "A"})

    def last_name_too_short(self):
        with pytest.raises(ValidationError):
            CoachUpdate.model_validate({"last_name": "N"})

    def test_first_name_too_long(self):
        with pytest.raises(ValidationError):
            CoachUpdate.model_validate({"first_name": "A" * 101})

    def test_last_name_too_long(self):
        with pytest.raises(ValidationError):
            CoachUpdate.model_validate({"last_name": "A" * 101})


class TestCoachRead:
    def test_valid(self):
        c = CoachRead.model_validate(
            {
                "id": 1,
                "first_name": "Annette",
                "last_name": "Nel",
                "club_id": 1,
                "is_head_coach": True,
            }
        )
        assert c.id == 1
        assert c.first_name == "Annette"
        assert c.last_name == "Nel"
        assert c.club_id == 1
        assert c.is_head_coach is True

    def test_from_orm_like_object(self):
        class ORMCoach:
            def __init__(self, id, first_name, last_name, club_id, is_head_coach):
                self.id = id
                self.first_name = first_name
                self.last_name = last_name
                self.club_id = club_id
                self.is_head_coach = is_head_coach

        orm_coach = ORMCoach(1, "Annette", "Nel", 1, True)
        c = CoachRead.model_validate(orm_coach)
        assert c.id == 1
        assert c.first_name == "Annette"
        assert c.last_name == "Nel"
        assert c.club_id == 1
        assert c.is_head_coach is True

    def test_missing_fields(self):
        with pytest.raises(ValidationError):
            CoachRead.model_validate(
                {"id": 1, "first_name": "Annette", "last_name": "Nel", "club_id": 1}
            )

    def test_missing_id(self):
        with pytest.raises(ValidationError):
            CoachRead.model_validate(
                {"first_name": "Annette", "last_name": "Nel", "club_id": 1, "is_head_coach": True}
            )

    def test_missing_club_id(self):
        with pytest.raises(ValidationError):
            CoachRead.model_validate(
                {"id": 1, "first_name": "Annette", "last_name": "Nel", "is_head_coach": True}
            )
