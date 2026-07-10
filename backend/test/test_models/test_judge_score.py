import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Judge, JudgeScore, Panel, Routine
from test.conftest import (
    make_gymnast,
    make_judge,
    make_judge_score,
    make_meet,
    make_meet_entry,
    make_routine,
)


def test_judge_score_create_with_required_fields(db_session):
    # Create a judge score with required fields
    judge_score = make_judge_score(db_session)

    db_session.commit()

    fetched = db_session.query(JudgeScore).first()
    assert fetched is not None
    assert fetched.routine_id == judge_score.routine_id
    assert fetched.judge_id == judge_score.judge_id
    assert fetched.value == judge_score.value
    assert fetched.panel == judge_score.panel


def test_judge_score_create_without_required_fields(db_session):
    # Create a judge score without required fields
    judge_score = JudgeScore(
        routine_id=None,
        judge_id=None,
        value=None,
        panel=None,
    )
    db_session.add(judge_score)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_judge_score_value_out_of_range(db_session):
    # Create a judge score with a value out of range
    # This will violate the check constraint on the value column (0.0 <= value <= 10.0)
    # Ensure there is at least one routine and one judge in the database
    meet_entry = make_meet_entry(
        db_session, meet=make_meet(db_session), gymnast=make_gymnast(db_session)
    )

    if not db_session.query(Routine).first():
        make_routine(db_session, meet_entry=meet_entry)
    if not db_session.query(Judge).first():
        make_judge(db_session)

    routine = db_session.query(Routine).first()
    judge = db_session.query(Judge).first()
    judge_score = JudgeScore(
        routine_id=routine.id,
        judge_id=judge.id,
        value=15.0,  # Invalid score value
        panel=Panel.execution,
    )
    db_session.add(judge_score)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_judge_score_value_not_multiple_of_0_05(db_session):
    # Create a judge score with a value that is not a multiple of 0.05
    # This will violate the check constraint on the value column (value % 0.05 = 0)
    # Ensure there is at least one routine and one judge in the database
    meet_entry = make_meet_entry(
        db_session, meet=make_meet(db_session), gymnast=make_gymnast(db_session)
    )

    if not db_session.query(Routine).first():
        make_routine(db_session, meet_entry=meet_entry)
    if not db_session.query(Judge).first():
        make_judge(db_session)

    routine = db_session.query(Routine).first()
    judge = db_session.query(Judge).first()
    judge_score = JudgeScore(
        routine_id=routine.id,
        judge_id=judge.id,
        value=9.43,  # Invalid score value
        panel=Panel.execution,
    )
    db_session.add(judge_score)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_create_judge_score_with_duplicate_routine_and_judge_not_allowed(db_session):
    # Create a judge score with a specific routine and judge
    # check the unique constraint on (routine_id, judge_id) is enforced
    meet_entry = make_meet_entry(
        db_session, meet=make_meet(db_session), gymnast=make_gymnast(db_session)
    )
    routine = make_routine(db_session, meet_entry=meet_entry)
    judge = make_judge(db_session)
    judge_score1 = JudgeScore(
        routine_id=routine.id,
        judge_id=judge.id,
        value=9.5,
        panel=Panel.execution,
    )
    db_session.add(judge_score1)
    db_session.commit()

    # Create another judge score with the same routine and judge
    judge_score2 = JudgeScore(
        routine_id=routine.id,
        judge_id=judge.id,
        value=9.6,
        panel=Panel.execution,
    )
    db_session.add(judge_score2)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_create_judge_score_same_routine_and_judge_different_panel_allowed(db_session):
    # Proves panel is actually part of uq_judge_score_routine_judge_panel -- if the
    # constraint were mistakenly just (routine_id, judge_id), this would raise instead.
    meet_entry = make_meet_entry(
        db_session, meet=make_meet(db_session), gymnast=make_gymnast(db_session)
    )
    routine = make_routine(db_session, meet_entry=meet_entry)
    judge = make_judge(db_session)
    judge_score1 = JudgeScore(
        routine_id=routine.id,
        judge_id=judge.id,
        value=9.5,
        panel=Panel.execution,
    )
    db_session.add(judge_score1)
    db_session.commit()

    judge_score2 = JudgeScore(
        routine_id=routine.id,
        judge_id=judge.id,
        value=9.0,
        panel=Panel.artistry,
    )
    db_session.add(judge_score2)
    db_session.commit()

    fetched = db_session.query(JudgeScore).filter_by(routine_id=routine.id, judge_id=judge.id).all()
    assert len(fetched) == 2


def test_delete_judge_with_scores_not_allowed(db_session):
    # Create a judge and a judge score
    meet_entry = make_meet_entry(
        db_session, meet=make_meet(db_session), gymnast=make_gymnast(db_session)
    )
    routine = make_routine(db_session, meet_entry=meet_entry)
    judge = make_judge(db_session)
    judge_score = JudgeScore(
        routine_id=routine.id,
        judge_id=judge.id,
        value=9.5,
        panel=Panel.execution,
    )
    db_session.add(judge_score)
    db_session.commit()

    # Attempt to delete the judge
    db_session.delete(judge)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_delete_routine_with_scores_allowed(db_session):
    # Create a routine and a judge score
    meet_entry = make_meet_entry(
        db_session, meet=make_meet(db_session), gymnast=make_gymnast(db_session)
    )
    routine = make_routine(db_session, meet_entry=meet_entry)
    judge = make_judge(db_session)
    judge_score = JudgeScore(
        routine_id=routine.id,
        judge_id=judge.id,
        value=9.5,
        panel=Panel.execution,
    )
    db_session.add(judge_score)
    db_session.commit()

    # Attempt to delete the routine
    db_session.delete(routine)
    db_session.commit()

    assert db_session.query(Routine).filter_by(id=routine.id).first() is None
    assert db_session.query(JudgeScore).filter_by(routine_id=routine.id).first() is None


def test_judge_difficulty_apparatus_score_gt_10_allowed(db_session):
    # Create a judge score with a value greater than 10.0 for difficulty panel
    meet_entry = make_meet_entry(
        db_session, meet=make_meet(db_session), gymnast=make_gymnast(db_session)
    )
    routine = make_routine(db_session, meet_entry=meet_entry)
    judge = make_judge(db_session)
    judge_score = JudgeScore(
        routine_id=routine.id,
        judge_id=judge.id,
        value=10.5,  # Invalid score value for difficulty panel
        panel=Panel.difficulty_apparatus,
    )
    db_session.add(judge_score)
    db_session.commit()

    assert db_session.query(JudgeScore).filter_by(id=judge_score.id).first() is not None


def test_judge_difficulty_body_gt_10_allowed(db_session):
    # Create a judge score with a value greater than 10.0 for difficulty body panel
    meet_entry = make_meet_entry(
        db_session, meet=make_meet(db_session), gymnast=make_gymnast(db_session)
    )
    routine = make_routine(db_session, meet_entry=meet_entry)
    judge = make_judge(db_session)
    judge_score = JudgeScore(
        routine_id=routine.id,
        judge_id=judge.id,
        value=11.0,  # Invalid score value for difficulty body panel
        panel=Panel.difficulty_body,
    )
    db_session.add(judge_score)
    db_session.commit()

    assert db_session.query(JudgeScore).filter_by(id=judge_score.id).first() is not None


def test_judge_score_negative_not_allowed(db_session):
    # Create a judge score with a negative value
    meet_entry = make_meet_entry(
        db_session, meet=make_meet(db_session), gymnast=make_gymnast(db_session)
    )
    routine = make_routine(db_session, meet_entry=meet_entry)
    judge = make_judge(db_session)
    judge_score = JudgeScore(
        routine_id=routine.id,
        judge_id=judge.id,
        value=-1.0,  # Invalid negative score value
        panel=Panel.execution,
    )
    db_session.add(judge_score)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_judge_score_value_is_0(db_session):
    # Create a judge score with a value of 0.0
    meet_entry = make_meet_entry(
        db_session, meet=make_meet(db_session), gymnast=make_gymnast(db_session)
    )
    routine = make_routine(db_session, meet_entry=meet_entry)
    judge = make_judge(db_session)
    judge_score = JudgeScore(
        routine_id=routine.id,
        judge_id=judge.id,
        value=0.0,  # Valid score value
        panel=Panel.execution,
    )
    db_session.add(judge_score)
    db_session.commit()

    assert db_session.query(JudgeScore).filter_by(id=judge_score.id).first() is not None
