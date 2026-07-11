"""Pydantic validation tests for the GroupCreate/GroupUpdate/GroupRead schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.group import GroupCreate, GroupRead, GroupUpdate


##-- GroupCreate Tests --
class TestGroupCreate:
    def test_group_create_valid(self):
        group = GroupCreate(club_id=1, name="Group A")
        assert group.club_id == 1
        assert group.name == "Group A"

    def test_group_create_strip_whitespace(self):
        group = GroupCreate(club_id=1, name="  Group A  ")
        assert group.name == "Group A"

    def test_group_create_name_too_short(self):
        with pytest.raises(ValidationError):
            GroupCreate(club_id=1, name="A")

    def test_group_create_name_required(self):
        with pytest.raises(ValidationError):
            GroupCreate.model_validate({"club_id": 1})

##-- GroupUpdate Tests --
class TestGroupUpdate:
    def test_group_update_all_optional(self):
        group = GroupUpdate.model_validate({})
        assert group.name is None

    def test_group_update_partial_name_only(self):
        group = GroupUpdate.model_validate({"name": "Group A"})
        assert group.name == "Group A"

    def test_group_update_strip_whitespace(self):
        group = GroupUpdate.model_validate({"name": "  Group A  "})
        assert group.name == "Group A"

    def test_group_update_name_too_short(self):
        with pytest.raises(ValidationError):
            GroupUpdate.model_validate({"name": "A"})

##-- GroupRead Tests --
class TestGroupRead:
    def test_group_read_schema(self):
        group_read = GroupRead.model_validate({
            "id": 1,
            "club_id": 1,
            "name": "Group A"
        })
        assert group_read.id == 1
        assert group_read.club_id == 1
        assert group_read.name == "Group A"

    def test_group_read_from_orm_like_object(self):
        class DummyGroup:
            def __init__(self, id, club_id, name):
                self.id = id
                self.club_id = club_id
                self.name = name

        dummy_group = DummyGroup(id=1, club_id=1, name="Group A")
        group_read = GroupRead.model_validate(dummy_group)
        assert group_read.id == 1
        assert group_read.club_id == 1
        assert group_read.name == "Group A"
