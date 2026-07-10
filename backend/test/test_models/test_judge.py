"""
Tests for the Judge model.
"""

import pytest
from sqlalchemy.exc import DataError, IntegrityError

from app.models import Judge
from test.conftest import make_judge


def test_judge_create_with_required_fields(db_session):
    judge = make_judge(db_session)

    db_session.commit()

    fetched = db_session.query(Judge).first()
    assert fetched is not None
    assert fetched.first_name == judge.first_name
    assert fetched.last_name == judge.last_name
    assert fetched.country_code == judge.country_code
    assert fetched.brevet == judge.brevet


def test_judge_create_without_required_fields(db_session):
    judge = Judge(
        first_name=None,
        last_name=None,
        country_code=None,
        brevet=None,
    )
    db_session.add(judge)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_judge_country_not_3_chars(db_session):
    judge = Judge(
        first_name="John",
        last_name="Doe",
        country_code="ABCD",  # Invalid ISO code
        brevet="A",
    )
    db_session.add(judge)

    with pytest.raises(DataError):
        db_session.commit()


def test_create_judge_with_duplicate_name_allowed(db_session):
    judge1 = Judge(
        first_name="John",
        last_name="Doe",
        country_code="USA",
        brevet="A",
    )
    db_session.add(judge1)
    db_session.commit()

    judge2 = Judge(
        first_name="John",
        last_name="Carpenter",
        country_code="CAN",
        brevet="B",
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
        brevet="A",
    )
    db_session.add(judge1)
    db_session.commit()

    judge2 = Judge(
        first_name="Bob",
        last_name="Smith",
        country_code="CAN",
        brevet="B",
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
        brevet="A",
    )
    db_session.add(judge1)
    db_session.commit()

    judge2 = Judge(
        first_name="David",
        last_name="Johnson",
        country_code="USA",  # Same country code
        brevet="B",
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
        brevet="A",
    )
    db_session.add(judge1)
    db_session.commit()

    judge2 = Judge(
        first_name="Eve",
        last_name="Adams",  # Same name
        country_code="USA",  # Same country code
        brevet="B",
    )
    db_session.add(judge2)

    with pytest.raises(IntegrityError):
        db_session.commit()
