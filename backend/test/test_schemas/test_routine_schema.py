import pytest
from pydantic import ValidationError

from app.models import Apparatus
from app.schemas.routine import RoutineCreate, RoutineRead, RoutineUpdate


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

class TestRoutineRead:
    def test_routine_read_from_model(self):
        routine_data = {
            "id": 1,
            "entry_id": 1,
            "apparatus": Apparatus.rope,
            "order_of_performance": 1,
        }
        routine_read = RoutineRead.model_validate(routine_data)
        assert routine_read.id == 1
        assert routine_read.entry_id == 1
        assert routine_read.apparatus == Apparatus.rope
        assert routine_read.order_of_performance == 1

    def test_routine_read_valid_data(self):
        routine_data = {
            "id": 1,
            "entry_id": 1,
            "apparatus": Apparatus.rope,
            "order_of_performance": 1,
        }
        routine_read = RoutineRead.model_validate(routine_data)
        assert routine_read.id == 1
        assert routine_read.entry_id == 1
        assert routine_read.apparatus == Apparatus.rope
        assert routine_read.order_of_performance == 1

    def test_routine_read_missing_order_of_performance(self):
        routine_data = {
            "id": 1,
            "entry_id": 1,
            "apparatus": Apparatus.ball,
        }
        routine_read = RoutineRead.model_validate(routine_data)
        assert routine_read.id == 1
        assert routine_read.entry_id == 1
        assert routine_read.apparatus == Apparatus.ball
        assert routine_read.order_of_performance is None

    def test_routine_read_invalid_apparatus(self):
        routine_data = {
            "id": 1,
            "entry_id": 1,
            "apparatus": "invalid_apparatus",
            "order_of_performance": 1,
        }
        with pytest.raises(ValidationError):
            RoutineRead.model_validate(routine_data)

    def test_routine_read_apparatus_from_string(self):
        routine_data = {
            "id": 1,
            "entry_id": 1,
            "apparatus": "clubs",
            "order_of_performance": 2,
        }
        routine_read = RoutineRead.model_validate(routine_data)
        assert routine_read.apparatus == Apparatus.clubs

    def test_routine_read_from_orm_model(self):
        class DummyRoutine:
            def __init__(self, id, entry_id, apparatus, order_of_performance):
                self.id = id
                self.entry_id = entry_id
                self.apparatus = apparatus
                self.order_of_performance = order_of_performance

        dummy_routine = DummyRoutine(
            id=1,
            entry_id=1,
            apparatus=Apparatus.hoop,
            order_of_performance=3,
        )
        routine_read = RoutineRead.model_validate(dummy_routine)
        assert routine_read.id == 1
        assert routine_read.entry_id == 1
        assert routine_read.apparatus == Apparatus.hoop
        assert routine_read.order_of_performance == 3

    def test_routine_read_missing_entry_id(self):
        routine_data = {
            "id": 1,
            "apparatus": Apparatus.rope,
            "order_of_performance": 1,
        }
        with pytest.raises(ValidationError):
            RoutineRead.model_validate(routine_data)
