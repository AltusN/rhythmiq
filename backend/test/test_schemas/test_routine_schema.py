"""
Pydantic validation tests for the RoutineCreate/RoutineUpdate/RoutineRead schemas,
plus RoutineScoreRead (the GET /routines/{id}/score response wrapper). penalty
defaults to 0 on Create (not None -- see app/schemas/routine.py) since the router
builds the model via model_dump() without exclude_unset.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models import Apparatus
from app.schemas.routine import RoutineCreate, RoutineRead, RoutineScoreRead, RoutineUpdate


class TestRoutineCreate:
    def test_routine_create_valid_routine_create(self):
        routine_data = {
            "entry_id": 1,
            "apparatus": Apparatus.rope,
            "order_of_performance": 1,
        }
        routine = RoutineCreate(**routine_data)
        assert routine.entry_id == 1
        assert routine.apparatus == Apparatus.rope
        assert routine.order_of_performance == 1

    def test_routine_create_penalty_defaults_to_zero(self):
        routine_data = {
            "entry_id": 1,
            "apparatus": Apparatus.rope,
        }
        routine = RoutineCreate(**routine_data)
        assert routine.penalty == Decimal("0")

    def test_routine_create_penalty_explicit_value(self):
        routine_data = {
            "entry_id": 1,
            "apparatus": Apparatus.rope,
            "penalty": "0.30",
        }
        routine = RoutineCreate(**routine_data)
        assert routine.penalty == Decimal("0.30")

    def test_routine_create_penalty_negative_rejected(self):
        routine_data = {
            "entry_id": 1,
            "apparatus": Apparatus.rope,
            "penalty": "-0.10",
        }
        with pytest.raises(ValidationError):
            RoutineCreate(**routine_data)

    def test_routine_create_penalty_not_a_multiple_of_0_05_rejected(self):
        routine_data = {
            "entry_id": 1,
            "apparatus": Apparatus.rope,
            "penalty": "0.31",
        }
        with pytest.raises(ValidationError):
            RoutineCreate(**routine_data)

    def test_routine_create_missing_order_of_performance(self):
        routine_data = {
            "entry_id": 1,
            "apparatus": Apparatus.ball,
        }
        routine = RoutineCreate(**routine_data)
        assert routine.entry_id == 1
        assert routine.apparatus == Apparatus.ball
        assert routine.order_of_performance is None

    def test_routine_create_invalid_apparatus(self):
        routine_data = {
            "entry_id": 1,
            "apparatus": "invalid_apparatus",
            "order_of_performance": 1,
        }
        with pytest.raises(ValidationError):
            RoutineCreate(**routine_data)

    def test_routine_create_negative_order_of_performance(self):
        routine_data = {
            "entry_id": 1,
            "apparatus": Apparatus.hoop,
            "order_of_performance": -1,
        }
        with pytest.raises(ValidationError):
            RoutineCreate(**routine_data)

    def test_routine_create_apparatus_from_string(self):
        routine_data = {
            "entry_id": 1,
            "apparatus": "clubs",
            "order_of_performance": 2,
        }
        routine = RoutineCreate(**routine_data)
        assert routine.apparatus == Apparatus.clubs

    def test_routine_ceate_entry_id_required(self):
        routine_data = {
            "apparatus": Apparatus.rope,
            "order_of_performance": 1,
        }
        with pytest.raises(ValidationError):
            RoutineCreate(**routine_data)

    def test_routine_create_invalid_apparatus_type(self):
        routine_data = {
            "entry_id": 1,
            "apparatus": 123,  # Invalid type, should be a string or Apparatus enum
            "order_of_performance": 1,
        }
        with pytest.raises(ValidationError):
            RoutineCreate.model_validate(routine_data)

    def test_routine_create_order_of_performance_zero(self):
        routine_data = {
            "entry_id": 1,
            "apparatus": Apparatus.hoop,
            "order_of_performance": 0,  # Invalid, should be >= 1
        }
        with pytest.raises(ValidationError):
            RoutineCreate.model_validate(routine_data)

    def test_routine_create_order_of_performance_greater_than_one(self):
        routine_data = {
            "entry_id": 1,
            "apparatus": Apparatus.hoop,
            "order_of_performance": 5,  # Valid, should be >= 1
        }
        routine = RoutineCreate.model_validate(routine_data)
        assert routine.order_of_performance == 5

    def test_routtine_create_freehand_apparatus(self):
        routine_data = {
            "entry_id": 1,
            "apparatus": Apparatus.freehand,
            "order_of_performance": 3,
        }
        routine = RoutineCreate.model_validate(routine_data)
        assert routine.apparatus == Apparatus.freehand


class TestRoutineUpdate:
    def test_routine_update_valid_order_of_performance(self):
        routine_data = {
            "order_of_performance": 2,
        }
        routine_update = RoutineUpdate(**routine_data)
        assert routine_update.order_of_performance == 2

    def test_routine_update_missing_order_of_performance(self):
        routine_data = {}
        routine_update = RoutineUpdate(**routine_data)
        assert routine_update.order_of_performance is None

    def test_routine_update_negative_order_of_performance(self):
        routine_data = {
            "order_of_performance": -1,
        }
        with pytest.raises(ValidationError):
            RoutineUpdate(**routine_data)

    def test_routine_update_order_of_performance_zero(self):
        routine_data = {
            "order_of_performance": 0,
        }
        with pytest.raises(ValidationError):
            RoutineUpdate(**routine_data)

    def test_routine_update_order_of_performance_greater_than_one(self):
        routine_data = {
            "order_of_performance": 3,
        }
        routine_update = RoutineUpdate(**routine_data)
        assert routine_update.order_of_performance == 3

    def test_routine_update_all_optional(self):
        routine_data = {
            "order_of_performance": None,
        }
        routine_update = RoutineUpdate(**routine_data)
        assert routine_update.order_of_performance is None

    def test_routine_update_clear_order_of_performance(self):
        routine_data = {
            "order_of_performance": None,
        }
        routine_update = RoutineUpdate(**routine_data)
        assert routine_update.order_of_performance is None

    def test_routine_update_penalty_missing_stays_none(self):
        # None here means "not provided" -- the router uses exclude_unset=True on PATCH,
        # so this leaves the stored penalty untouched rather than clearing it to 0.
        routine_update = RoutineUpdate()
        assert routine_update.penalty is None

    def test_routine_update_penalty_valid_value(self):
        routine_update = RoutineUpdate(penalty="0.50")
        assert routine_update.penalty == Decimal("0.50")

    def test_routine_update_penalty_negative_rejected(self):
        with pytest.raises(ValidationError):
            RoutineUpdate(penalty="-0.05")

    def test_routine_update_penalty_not_a_multiple_of_0_05_rejected(self):
        with pytest.raises(ValidationError):
            RoutineUpdate(penalty="0.32")


class TestRoutineRead:
    def test_routine_read_from_model(self):
        routine_data = {
            "id": 1,
            "entry_id": 1,
            "apparatus": Apparatus.rope,
            "order_of_performance": 1,
            "penalty": "0",
        }
        routine_read = RoutineRead.model_validate(routine_data)
        assert routine_read.id == 1
        assert routine_read.entry_id == 1
        assert routine_read.apparatus == Apparatus.rope
        assert routine_read.order_of_performance == 1
        assert routine_read.penalty == Decimal("0")

    def test_routine_read_valid_data(self):
        routine_data = {
            "id": 1,
            "entry_id": 1,
            "apparatus": Apparatus.rope,
            "order_of_performance": 1,
            "penalty": "0.30",
        }
        routine_read = RoutineRead.model_validate(routine_data)
        assert routine_read.id == 1
        assert routine_read.entry_id == 1
        assert routine_read.apparatus == Apparatus.rope
        assert routine_read.order_of_performance == 1
        assert routine_read.penalty == Decimal("0.30")

    def test_routine_read_missing_order_of_performance(self):
        routine_data = {
            "id": 1,
            "entry_id": 1,
            "apparatus": Apparatus.ball,
            "penalty": "0",
        }
        routine_read = RoutineRead.model_validate(routine_data)
        assert routine_read.id == 1
        assert routine_read.entry_id == 1
        assert routine_read.apparatus == Apparatus.ball
        assert routine_read.order_of_performance is None

    def test_routine_read_missing_penalty_rejected(self):
        # penalty is required in RoutineRead -- always present on the model
        # (server_default="0"), so an ORM-backed response should never omit it.
        routine_data = {
            "id": 1,
            "entry_id": 1,
            "apparatus": Apparatus.ball,
            "order_of_performance": 1,
        }
        with pytest.raises(ValidationError):
            RoutineRead.model_validate(routine_data)

    def test_routine_read_invalid_apparatus(self):
        routine_data = {
            "id": 1,
            "entry_id": 1,
            "apparatus": "invalid_apparatus",
            "order_of_performance": 1,
            "penalty": "0",
        }
        with pytest.raises(ValidationError):
            RoutineRead.model_validate(routine_data)

    def test_routine_read_apparatus_from_string(self):
        routine_data = {
            "id": 1,
            "entry_id": 1,
            "apparatus": "clubs",
            "order_of_performance": 2,
            "penalty": "0",
        }
        routine_read = RoutineRead.model_validate(routine_data)
        assert routine_read.apparatus == Apparatus.clubs

    def test_routine_read_from_orm_model(self):
        class DummyRoutine:
            def __init__(self, id, entry_id, apparatus, order_of_performance, penalty):
                self.id = id
                self.entry_id = entry_id
                self.apparatus = apparatus
                self.order_of_performance = order_of_performance
                self.penalty = penalty

        dummy_routine = DummyRoutine(
            id=1,
            entry_id=1,
            apparatus=Apparatus.hoop,
            order_of_performance=3,
            penalty=Decimal("0"),
        )
        routine_read = RoutineRead.model_validate(dummy_routine)
        assert routine_read.id == 1
        assert routine_read.entry_id == 1
        assert routine_read.apparatus == Apparatus.hoop
        assert routine_read.order_of_performance == 3
        assert routine_read.penalty == Decimal("0")

    def test_routine_read_missing_entry_id(self):
        routine_data = {
            "id": 1,
            "apparatus": Apparatus.rope,
            "order_of_performance": 1,
            "penalty": "0",
        }
        with pytest.raises(ValidationError):
            RoutineRead.model_validate(routine_data)


class TestRoutineScoreRead:
    def test_routine_score_read_valid_data(self):
        score_data = {
            "routine_id": 1,
            "d_score": "5.30",
            "a_score": "9.25",
            "e_score": "8.65",
            "final_score": "0.00",
            "penalty": "0.30",
            "total": "22.90",
        }
        score = RoutineScoreRead(**score_data)
        assert score.routine_id == 1
        assert score.d_score == Decimal("5.30")
        assert score.a_score == Decimal("9.25")
        assert score.e_score == Decimal("8.65")
        assert score.final_score == Decimal("0.00")
        assert score.penalty == Decimal("0.30")
        assert score.total == Decimal("22.90")

    def test_routine_score_read_missing_field_rejected(self):
        score_data = {
            "routine_id": 1,
            "d_score": "5.30",
            "a_score": "9.25",
            "e_score": "8.65",
            "penalty": "0.30",
            # total missing
        }
        with pytest.raises(ValidationError):
            RoutineScoreRead(**score_data)
