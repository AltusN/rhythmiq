"""
Tests for the Judge model.
"""

import pytest
from sqlalchemy.exc import DataError, IntegrityError

from app.models import Judge, JudgeCategory
from test.conftest import make_judge


def test_judge_create_with_required_fields(db_session):
    judge = make_judge(db_session)

    db_session.commit()

    fetched = db_session.query(Judge).first()
    assert fetched is not None
    assert fetched.first_name == judge.first_name
    assert fetched.last_name == judge.last_name
    assert fetched.country_code == judge.country_code
    assert fetched.category == judge.category


def test_judge_create_without_required_fields(db_session):
    judge = Judge(
        first_name=None,
        last_name=None,
        country_code=None,
        category=None,
    )
    db_session.add(judge)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_judge_country_not_3_chars(db_session):
    judge = Judge(
        first_name="John",
        last_name="Doe",
        country_code="ABCD",  # Invalid ISO code
        category=JudgeCategory.category_1,
    )
    db_session.add(judge)

    with pytest.raises(DataError):
        db_session.commit()


def test_create_judge_with_duplicate_name_allowed(db_session):
    judge1 = Judge(
        first_name="John",
        last_name="Doe",
        country_code="USA",
        category=JudgeCategory.category_1,
    )
    db_session.add(judge1)
    db_session.commit()

    judge2 = Judge(
        first_name="John",
        last_name="Carpenter",
        country_code="CAN",
        category=JudgeCategory.category_2,
    )
    db_session.add(judge2)
    db_session.commit()

    fetched_judges = db_session.query(Judge).filter_by(first_name="John").all()
    assert len(fetched_judges) == 2


def test_create_judge_with_same_last_name_allowed(db_session):
    judge1 = Judge(
        first_name="Alice",
        last_name="Smith",
        country_code="USA",
        category=JudgeCategory.category_1,
    )
    db_session.add(judge1)
    db_session.commit()

    judge2 = Judge(
        first_name="Bob",
        last_name="Smith",
        country_code="CAN",
        category=JudgeCategory.category_2,
    )
    db_session.add(judge2)
    db_session.commit()

    fetched_judges = db_session.query(Judge).filter_by(last_name="Smith").all()
    assert len(fetched_judges) == 2


def test_create_judge_with_same_country_code_allowed(db_session):
    judge1 = Judge(
        first_name="Charlie",
        last_name="Brown",
        country_code="USA",
        category=JudgeCategory.category_1,
    )
    db_session.add(judge1)
    db_session.commit()

    judge2 = Judge(
        first_name="David",
        last_name="Johnson",
        country_code="USA",  # Same country code
        category=JudgeCategory.category_2,
    )
    db_session.add(judge2)
    db_session.commit()

    fetched_judges = db_session.query(Judge).filter_by(country_code="USA").all()
    assert len(fetched_judges) == 2


def test_create_judge_with_same_name_and_country_not_allowed(db_session):
    judge1 = Judge(
        first_name="Eve",
        last_name="Adams",
        country_code="USA",
        category=JudgeCategory.category_1,
    )
    db_session.add(judge1)
    db_session.commit()

    judge2 = Judge(
        first_name="Eve",
        last_name="Adams",  # Same name
        country_code="USA",  # Same country code
        category=JudgeCategory.category_2,
    )
    db_session.add(judge2)

    with pytest.raises(IntegrityError):
        db_session.commit()


class TestJudgeCategory:
    """
    FIG General Judges' Rules 2025-2028 art. 2.6 defines exactly four judging
    categories, 1 (highest) to 4 (lowest). See also RG Specific Judges' Rules
    art. 2.5, which reproduces the same table.
    """

    def test_exactly_four_categories_highest_first(self):
        assert [c.value for c in JudgeCategory] == [
            "category_1",
            "category_2",
            "category_3",
            "category_4",
        ]

    def test_category_persists(self, db_session):
        judge = make_judge(db_session, category=JudgeCategory.category_1)
        db_session.commit()
        db_session.refresh(judge)
        assert judge.category is JudgeCategory.category_1

    def test_category_is_optional(self, db_session):
        """
        Nullable on purpose: the FIG scale only covers category holders, and the rules
        list "national level" as a rank below Category 3, so nationally-graded judges
        have no FIG category to record.
        """
        judge = make_judge(db_session, category=None)
        db_session.commit()
        db_session.refresh(judge)
        assert judge.category is None
