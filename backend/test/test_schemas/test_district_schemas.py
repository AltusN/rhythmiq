import pytest
from pydantic import ValidationError

from app.schemas.district import DistrictCreate, DistrictUpdate, DistrictRead

# -- DistrictCreate Tests --
class TestDistrictCreate:
    def test_valid(self):
        d = DistrictCreate(name="Gauteng", abbreviation="GP")
        assert d.name == "Gauteng"
        assert d.abbreviation == "GP"
    
    def test_strip_whitespace(self):
        d = DistrictCreate(name="  Gauteng  ", abbreviation="  GP  ")
        assert d.name == "Gauteng"
        assert d.abbreviation == "GP"

    def test_name_too_short(self):
        with pytest.raises(ValidationError):
            DistrictCreate(name="A", abbreviation="GP")

    def test_name_required(self):
        with pytest.raises(ValidationError):
            DistrictCreate.model_validate({"abbreviation": "GP"})
        
    def test_abbreviation_too_short(self):
        with pytest.raises(ValidationError):
            DistrictCreate.model_validate({"name": "Gauteng", "abbreviation": ""})

    def test_abbreviation_required(self):
        with pytest.raises(ValidationError):
            DistrictCreate.model_validate({"name": "Gauteng"})

    def test_abbreviation_too_long(self):
        with pytest.raises(ValidationError):
            DistrictCreate.model_validate({"name": "Gauteng", "abbreviation": "TOOLONGABBREV"}) 

    def test_name_strip_too_short_after_strip(self):
        with pytest.raises(ValidationError):
            DistrictCreate(name="  A  ", abbreviation="GP")

#-- DistrictUpdate Tests --
class TestDistrictUpdate:
    def test_all_optional(self):
        d = DistrictUpdate.model_validate({})
        assert d.name is None
        assert d.abbreviation is None
    
    def test_partial_name_only(self):
        d = DistrictUpdate.model_validate({"name": "Gauteng"})
        assert d.name == "Gauteng"
        assert d.abbreviation is None

    def test_partial_abbreviation_only(self):
        d = DistrictUpdate.model_validate({"abbreviation": "GP"})
        assert d.name is None
        assert d.abbreviation == "GP"

    def test_valid(self):
        d = DistrictUpdate.model_validate({"name": "Gauteng", "abbreviation": "GP"})
        assert d.name == "Gauteng"
        assert d.abbreviation == "GP"
    
    def test_strip_whitespace(self):
        d = DistrictUpdate.model_validate({"name": "  Gauteng  ", "abbreviation": "  GP  "})
        assert d.name == "Gauteng"
        assert d.abbreviation == "GP"

    def test_name_too_short(self):
        with pytest.raises(ValidationError):
            DistrictUpdate.model_validate({"name": "A", "abbreviation": "GP"})

    def test_abbreviation_too_short(self):
        with pytest.raises(ValidationError):
            DistrictUpdate.model_validate({"name": "Gauteng", "abbreviation": ""})

class TestDistrictRead:
    def test_valid(self):
        d = DistrictRead.model_validate({"id": 1, "name": "Gauteng", "abbreviation": "GP"})
        assert d.id == 1
        assert d.name == "Gauteng"
        assert d.abbreviation == "GP"
    
    def test_missing_fields(self):
        with pytest.raises(ValidationError):
            DistrictRead.model_validate({"id": 1, "name": "Gauteng"})
    
    def test_missing_id(self):
        with pytest.raises(ValidationError):
            DistrictRead.model_validate({"name": "Gauteng", "abbreviation": "GP"})  

    def test_from_orm_like_object(self):
        class ORMObject:
            def __init__(self, id, name, abbreviation):
                self.id = id
                self.name = name
                self.abbreviation = abbreviation
        
        orm_obj = ORMObject(id=1, name="Gauteng", abbreviation="GP")
        d = DistrictRead.model_validate(orm_obj)
        assert d.id == 1
        assert d.name == "Gauteng"
        assert d.abbreviation == "GP"