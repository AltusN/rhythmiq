"""
Pydantic validation tests for the JudgeScoreCreate/JudgeScoreUpdate/JudgeScoreRead
schemas, including the Create-only model_validator that caps artistry/execution at
10.0 (difficulty_body/difficulty_apparatus are uncapped).
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models import Panel
from app.schemas.judge_score import JudgeScoreCreate, JudgeScoreRead, JudgeScoreUpdate


class TestJudgeScoreCreate:
    def test_valid_score(self):
        data = {
            "routine_id": 1,
            "judge_id": 1,
            "panel": Panel.execution,
            "value": 9.4,
        }
        score = JudgeScoreCreate.model_validate(data)
        assert score.routine_id == 1
        assert score.judge_id == 1
        assert score.panel == Panel.execution
        assert score.value == Decimal("9.4")

    def test_invalid_score_exceeds_cap(self):
        data = {
            "routine_id": 1,
            "judge_id": 1,
            "panel": Panel.artistry,
            "value": 10.5,
        }
        with pytest.raises(ValidationError) as exc_info:
            JudgeScoreCreate.model_validate(data)
        assert "Artistry and execution scores cannot exceed 10.0" in str(exc_info.value)

    def test_invalid_score_negative(self):
        data = {
            "routine_id": 1,
            "judge_id": 1,
            "panel": Panel.execution,
            "value": -1.0,
        }
        with pytest.raises(ValidationError) as exc_info:
            JudgeScoreCreate.model_validate(data)
        assert "Input should be greater than or equal to 0" in str(exc_info.value)

    def test_invalid_score_not_multiple_of_0_05(self):
        data = {
            "routine_id": 1,
            "judge_id": 1,
            "panel": Panel.execution,
            "value": 9.43,
        }
        with pytest.raises(ValidationError):
            JudgeScoreCreate.model_validate(data)

    def test_create_score_invalid_routine_id(self):
        data = {
            "routine_id": "invalid",
            "judge_id": 1,
            "panel": Panel.execution,
            "value": 9.4,
        }
        with pytest.raises(ValidationError):
            JudgeScoreCreate.model_validate(data)

    def test_create_score_invalid_judge_id(self):
        data = {
            "routine_id": 1,
            "judge_id": "invalid",
            "panel": Panel.execution,
            "value": 9.4,
        }
        with pytest.raises(ValidationError):
            JudgeScoreCreate.model_validate(data)

    def test_create_score_invalid_panel(self):
        data = {
            "routine_id": 1,
            "judge_id": 1,
            "panel": "invalid",
            "value": 9.4,
        }
        with pytest.raises(ValidationError):
            JudgeScoreCreate.model_validate(data)

    def test_difficulty_body_score_is_not_capped_at_10(self):
        # This is the case that catches the exact regression this validator was
        # written to fix: only artistry/execution cap at 10, difficulty doesn't.
        data = {
            "routine_id": 1,
            "judge_id": 1,
            "panel": Panel.difficulty_body,
            "value": 15.30,
        }
        score = JudgeScoreCreate.model_validate(data)
        assert score.value == Decimal("15.30")

    def test_difficulty_apparatus_score_is_not_capped_at_10(self):
        data = {
            "routine_id": 1,
            "judge_id": 1,
            "panel": Panel.difficulty_apparatus,
            "value": 12.60,
        }
        score = JudgeScoreCreate.model_validate(data)
        assert score.value == Decimal("12.60")

    def test_capped_panel_score_of_exactly_10_is_accepted(self):
        # The validator rejects value > 10, not >= 10 -- the boundary itself must pass.
        data = {
            "routine_id": 1,
            "judge_id": 1,
            "panel": Panel.artistry,
            "value": 10.00,
        }
        score = JudgeScoreCreate.model_validate(data)
        assert score.value == Decimal("10")

    def test_create_score_panel_accepts_plain_string(self):
        # Real HTTP JSON bodies send the panel as a string, not a Panel member directly.
        data = {
            "routine_id": 1,
            "judge_id": 1,
            "panel": "execution",
            "value": 9.4,
        }
        score = JudgeScoreCreate.model_validate(data)
        assert score.panel == Panel.execution

    def test_create_score_missing_routine_id(self):
        data = {"judge_id": 1, "panel": Panel.execution, "value": 9.4}
        with pytest.raises(ValidationError):
            JudgeScoreCreate.model_validate(data)

    def test_create_score_missing_judge_id(self):
        data = {"routine_id": 1, "panel": Panel.execution, "value": 9.4}
        with pytest.raises(ValidationError):
            JudgeScoreCreate.model_validate(data)

    def test_create_score_missing_panel(self):
        data = {"routine_id": 1, "judge_id": 1, "value": 9.4}
        with pytest.raises(ValidationError):
            JudgeScoreCreate.model_validate(data)

    def test_create_score_missing_value(self):
        data = {"routine_id": 1, "judge_id": 1, "panel": Panel.execution}
        with pytest.raises(ValidationError):
            JudgeScoreCreate.model_validate(data)


class TestJudgeScoreUpdate:
    def test_valid_update(self):
        data = {
            "value": 8.5,
        }
        score_update = JudgeScoreUpdate.model_validate(data)
        assert score_update.value == Decimal("8.5")

    def test_invalid_update_negative(self):
        data = {
            "value": -1.0,
        }
        with pytest.raises(ValidationError) as exc_info:
            JudgeScoreUpdate.model_validate(data)
        assert "Input should be greater than or equal to 0" in str(exc_info.value)

    def test_invalid_update_not_multiple_of_0_05(self):
        data = {
            "value": 8.43,
        }
        with pytest.raises(ValidationError):
            JudgeScoreUpdate.model_validate(data)

    def test_update_exclude_unset_only_includes_provided_fields(self):
        # The router builds updates via payload.model_dump(exclude_unset=True) --
        # this is the actual contract the JudgeScoreUpdate router handler depends on.
        score_update = JudgeScoreUpdate.model_validate({"value": 8.5})
        assert score_update.model_dump(exclude_unset=True) == {"value": Decimal("8.5")}


class TestJudgeScoreRead:
    def test_read_score(self):
        data = {
            "id": 1,
            "routine_id": 1,
            "judge_id": 1,
            "panel": Panel.execution,
            "value": Decimal("9.4"),
        }
        score_read = JudgeScoreRead.model_validate(data)
        assert score_read.id == 1
        assert score_read.routine_id == 1
        assert score_read.judge_id == 1
        assert score_read.panel == Panel.execution
        assert score_read.value == Decimal("9.4")

    def test_read_score_invalid_panel(self):
        data = {
            "id": 1,
            "routine_id": 1,
            "judge_id": 1,
            "panel": "invalid",
            "value": Decimal("9.4"),
        }
        with pytest.raises(ValidationError):
            JudgeScoreRead.model_validate(data)

    def test_read_score_invalid_value(self):
        data = {
            "id": 1,
            "routine_id": 1,
            "judge_id": 1,
            "panel": Panel.execution,
            "value": "invalid",
        }
        with pytest.raises(ValidationError):
            JudgeScoreRead.model_validate(data)

    def test_score_read_from_orm_object(self):
        class MockScore:
            def __init__(self, id, routine_id, judge_id, panel, value):
                self.id = id
                self.routine_id = routine_id
                self.judge_id = judge_id
                self.panel = panel
                self.value = value

        mock_score = MockScore(1, 1, 1, Panel.execution, Decimal("9.4"))
        score_read = JudgeScoreRead.model_validate(mock_score)
        assert score_read.id == 1
        assert score_read.routine_id == 1
        assert score_read.judge_id == 1
        assert score_read.panel == Panel.execution
        assert score_read.value == Decimal("9.4")
