"""
Pydantic validation tests for the RoutineProfileCreate/RoutineProfileUpdate/
RoutineProfileRead schemas, including the model_validator requiring exactly one of
gymnast_id/group_id (same pattern as MeetEntry).
"""

import pytest
from pydantic import ValidationError

from app.models import Apparatus, Level
from app.schemas.routine_profile import (
    RoutineProfileCreate,
    RoutineProfileRead,
    RoutineProfileUpdate,
)


class TestRoutineProfileCreate:
    def test_routine_profile_create_valid_gymnast_id(self):
        routine_profile_data = {
            "gymnast_id": 1,
            "apparatus": Apparatus.rope,
            "level": Level.level_1,
            "music_url": "https://example.com/music.mp3",
            "choreography_notes": "Some notes about the choreography.",
        }
        routine_profile = RoutineProfileCreate(**routine_profile_data)
        assert routine_profile.gymnast_id == 1
        assert routine_profile.apparatus == Apparatus.rope
        assert routine_profile.level == Level.level_1
        assert routine_profile.music_url == "https://example.com/music.mp3"
        assert routine_profile.choreography_notes == "Some notes about the choreography."

    def test_routine_profile_create_valid_group_id(self):
        routine_profile_data = {
            "group_id": 2,
            "apparatus": Apparatus.hoop,
            "level": Level.level_2,
            "music_url": "https://example.com/music2.mp3",
            "choreography_notes": "Some notes about the group choreography.",
        }
        routine_profile = RoutineProfileCreate(**routine_profile_data)
        assert routine_profile.group_id == 2
        assert routine_profile.apparatus == Apparatus.hoop
        assert routine_profile.level == Level.level_2
        assert routine_profile.music_url == "https://example.com/music2.mp3"
        assert routine_profile.choreography_notes == "Some notes about the group choreography."

    def test_routine_profile_create_missing_gymnast_and_group(self):
        routine_profile_data = {
            "apparatus": Apparatus.ball,
            "level": Level.level_3,
            "music_url": "https://example.com/music3.mp3",
            "choreography_notes": "Some notes about the choreography.",
        }
        with pytest.raises(ValidationError) as exc_info:
            RoutineProfileCreate(**routine_profile_data)
        assert "Either gymnast_id or group_id must be provided." in str(exc_info.value)

    def test_routine_profile_create_both_gymnast_and_group(self):
        routine_profile_data = {
            "gymnast_id": 1,
            "group_id": 2,
            "apparatus": Apparatus.clubs,
            "level": Level.level_4,
            "music_url": "https://example.com/music4.mp3",
            "choreography_notes": "Some notes about the choreography.",
        }
        with pytest.raises(ValidationError) as exc_info:
            RoutineProfileCreate(**routine_profile_data)
        assert "Only one of gymnast_id or group_id can be provided." in str(exc_info.value)

    def test_routine_profile_create_missing_apparatus(self):
        routine_profile_data = {
            "gymnast_id": 1,
            "level": Level.level_1,
        }
        with pytest.raises(ValidationError):
            RoutineProfileCreate(**routine_profile_data)

    def test_routine_profile_create_missing_level(self):
        routine_profile_data = {
            "gymnast_id": 1,
            "apparatus": Apparatus.rope,
        }
        with pytest.raises(ValidationError):
            RoutineProfileCreate(**routine_profile_data)

    def test_routine_profile_create_invalid_apparatus(self):
        routine_profile_data = {
            "gymnast_id": 1,
            "apparatus": "invalid_apparatus",
            "level": Level.level_1,
        }
        with pytest.raises(ValidationError):
            RoutineProfileCreate(**routine_profile_data)

    def test_routine_profile_create_invalid_apparatus_type(self):
        routine_profile_data = {
            "gymnast_id": 1,
            "apparatus": 123,
            "level": Level.level_1,
        }
        with pytest.raises(ValidationError):
            RoutineProfileCreate(**routine_profile_data)

    def test_routine_profile_create_choreography_notes_too_long(self):
        routine_profile_data = {
            "gymnast_id": 1,
            "apparatus": Apparatus.rope,
            "level": Level.level_1,
            "choreography_notes": "a" * 501,
        }
        with pytest.raises(ValidationError):
            RoutineProfileCreate(**routine_profile_data)


class TestRoutineProfileUpdate:
    def test_routine_profile_update_all_fields_optional(self):
        routine_profile = RoutineProfileUpdate.model_validate({})
        assert routine_profile.music_url is None
        assert routine_profile.choreography_notes is None

    def test_routine_profile_update_accepts_music_url(self):
        routine_profile = RoutineProfileUpdate.model_validate(
            {"music_url": "https://example.com/music.mp3"}
        )
        assert routine_profile.music_url == "https://example.com/music.mp3"

    def test_routine_profile_update_accepts_choreography_notes(self):
        routine_profile = RoutineProfileUpdate.model_validate(
            {"choreography_notes": "Updated notes"}
        )
        assert routine_profile.choreography_notes == "Updated notes"

    def test_routine_profile_update_accepts_null_music_url(self):
        routine_profile = RoutineProfileUpdate.model_validate({"music_url": None})
        assert routine_profile.music_url is None

    def test_routine_profile_update_accepts_null_choreography_notes(self):
        routine_profile = RoutineProfileUpdate.model_validate({"choreography_notes": None})
        assert routine_profile.choreography_notes is None

    def test_routing_profile_update_notes_too_long(self):
        long_notes = "a" * 501  # 501 characters
        with pytest.raises(ValidationError):
            RoutineProfileUpdate.model_validate({"choreography_notes": long_notes})

    def test_routine_profile_update_ignores_locked_fields(self):
        # gymnast_id/group_id/apparatus/level aren't part of RoutineProfileUpdate, so
        # sending them should be silently dropped rather than erroring or leaking through.
        routine_profile = RoutineProfileUpdate.model_validate(
            {
                "gymnast_id": 999,
                "group_id": 999,
                "apparatus": Apparatus.hoop,
                "level": Level.level_4,
                "music_url": "https://example.com/music.mp3",
            }
        )
        assert not hasattr(routine_profile, "gymnast_id")
        assert not hasattr(routine_profile, "group_id")
        assert not hasattr(routine_profile, "apparatus")
        assert not hasattr(routine_profile, "level")
        assert routine_profile.music_url == "https://example.com/music.mp3"


class TestRoutineProfileRead:
    def test_routine_profile_read(self):
        routine_profile_data = {
            "id": 1,
            "gymnast_id": 1,
            "group_id": None,
            "apparatus": Apparatus.rope,
            "level": Level.level_1,
            "music_url": "https://example.com/music.mp3",
            "choreography_notes": "Some notes about the choreography.",
        }
        routine_profile = RoutineProfileRead.model_validate(routine_profile_data)
        assert routine_profile.id == 1
        assert routine_profile.gymnast_id == 1
        assert routine_profile.group_id is None
        assert routine_profile.apparatus == Apparatus.rope
        assert routine_profile.level == Level.level_1
        assert routine_profile.music_url == "https://example.com/music.mp3"
        assert routine_profile.choreography_notes == "Some notes about the choreography."

    def test_routine_profile_read_with_group(self):
        routine_profile_data = {
            "id": 2,
            "gymnast_id": None,
            "group_id": 2,
            "apparatus": Apparatus.hoop,
            "level": Level.level_2,
            "music_url": "https://example.com/music2.mp3",
            "choreography_notes": "Some notes about the group choreography.",
        }
        routine_profile = RoutineProfileRead.model_validate(routine_profile_data)
        assert routine_profile.id == 2
        assert routine_profile.gymnast_id is None
        assert routine_profile.group_id == 2
        assert routine_profile.apparatus == Apparatus.hoop
        assert routine_profile.level == Level.level_2
        assert routine_profile.music_url == "https://example.com/music2.mp3"
        assert routine_profile.choreography_notes == "Some notes about the group choreography."

    def test_routine_profile_read_from_orm_object(self):
        class DummyRoutineProfile:
            def __init__(
                self, id, gymnast_id, group_id, apparatus, level, music_url, choreography_notes
            ):
                self.id = id
                self.gymnast_id = gymnast_id
                self.group_id = group_id
                self.apparatus = apparatus
                self.level = level
                self.music_url = music_url
                self.choreography_notes = choreography_notes

        dummy_routine_profile = DummyRoutineProfile(
            id=1,
            gymnast_id=1,
            group_id=None,
            apparatus=Apparatus.rope,
            level=Level.level_1,
            music_url="https://example.com/music.mp3",
            choreography_notes="Some notes about the choreography.",
        )
        routine_profile_read = RoutineProfileRead.model_validate(dummy_routine_profile)
        assert routine_profile_read.id == 1
        assert routine_profile_read.gymnast_id == 1
        assert routine_profile_read.group_id is None
        assert routine_profile_read.apparatus == Apparatus.rope
        assert routine_profile_read.level == Level.level_1
        assert routine_profile_read.music_url == "https://example.com/music.mp3"
        assert routine_profile_read.choreography_notes == "Some notes about the choreography."

    def test_routine_profile_read_missing_apparatus(self):
        routine_profile_data = {
            "id": 1,
            "gymnast_id": 1,
            "group_id": None,
            "level": Level.level_1,
            "music_url": "https://example.com/music.mp3",
            "choreography_notes": "Some notes about the choreography.",
        }
        with pytest.raises(ValidationError):
            RoutineProfileRead.model_validate(routine_profile_data)

    def test_routine_profile_read_invalid_apparatus(self):
        routine_profile_data = {
            "id": 1,
            "gymnast_id": 1,
            "group_id": None,
            "apparatus": "invalid_apparatus",
            "level": Level.level_1,
            "music_url": "https://example.com/music.mp3",
            "choreography_notes": "Some notes about the choreography.",
        }
        with pytest.raises(ValidationError):
            RoutineProfileRead.model_validate(routine_profile_data)
