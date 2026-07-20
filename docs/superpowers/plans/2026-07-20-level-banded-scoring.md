# Level-Banded Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the shipped two-band `E_ONLY_LEVELS` rule with the three-band scoring model (levels 1–3 pre-aggregated, 4–7 `avg(DB) + E`, 8+ full FIG), including a new `Panel.final`, per-band medal systems, and the E deduction round trip in the score form.

**Architecture:** One declarative band→profile table in `app/scoring.py`, mirrored in `frontend/src/lib/score-math.ts`. Every band-dependent decision — panel validity, D combination, tie-breaking, medal mode, form box layout, required judge slots — is derived from that table rather than re-implemented per call site. `Panel.final` is a new enum member (hand-written migration) so that levels 1–3's single out-of-13 mark never has to masquerade as an execution score.

**Tech Stack:** FastAPI + Pydantic v2 + SQLAlchemy 2.0 + Alembic + Postgres (backend); React 19 + Vite + TanStack Query + React Hook Form + Vitest/Testing Library/MSW (frontend).

**Source spec:** `docs/superpowers/specs/2026-07-20-level-banded-scoring-design.md` — read it before starting. It is complete and has no open questions.

## Global Constraints

- Commit subjects MUST start with one of `feat:` / `fix:` / `chore:` / `docs:` / `test:`.
- Backend commands run from `backend/`; `make` targets run from the repo root.
- Enum values are never added by autogenerate — every enum change needs a hand-written `op.execute("ALTER TYPE ... ADD VALUE ...")` migration (CLAUDE.md).
- `app/scoring.py` and `frontend/src/lib/score-math.ts` mirror each other. Any change to one requires the matching change to the other, with worked-example tests kept in sync.
- Run `make types` from the repo root after any backend schema/router change and commit `frontend/src/api/schema.d.ts`.
- Backend lint/format: `ruff check .` and `ruff format .` from `backend/`.
- The three bands, verbatim from the spec:
  - **Levels 1–3:** one final mark from one judge, recorded as entered, max **13**. Medal by **score cutoff**. No tie-break.
  - **Levels 4–7:** DB1, DB2 + E1, E2 → `average(DB) + E`, max **13**. Medal by **placement**. No tie-break.
  - **Levels 8+:** DB, DA, A1, A2, E1–E4 → `(DB + DA) + average(A) + trimmedMean(E)`. Medal by **placement**. Tie-break on **highest E**.
- Execution is **always a score out of 10** in the database, at every level. The form speaks deductions; the API speaks scores; conversion happens only at the form boundary, in **both** directions.
- Levels 1–3 marks are **not** deductions — no conversion in either direction for that band.
- Medals for placement bands go to the first three **distinct rank values**; everyone sharing a rank shares its medal. Never `rank <= 3`.
- Competition ranking (1,2,2,4) itself is unchanged.

---

### Task 1: `Panel.final` — enum member, value cap, migration

Levels 1–3 store a single finished mark out of 13. It gets its own `Panel` member so that the `<= 10` cap on execution stays a true invariant at every level (spec: "Decision: a distinct `Panel.final` for levels 1–3").

**Files:**
- Modify: `backend/app/models.py:103-110` (`Panel` enum), `backend/app/models.py:212-215` (`ck_judge_score_panel_value_cap`)
- Create: `backend/migrations/versions/c1a7e4b90f22_add_final_panel_for_levels_1_3.py`
- Modify: `frontend/src/api/schema.d.ts` (regenerated, not hand-edited)
- Test: `backend/test/test_models/test_judge_score.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `Panel.final` (value `"final"`), usable everywhere `Panel` is imported. DB constraint `ck_judge_score_panel_value_cap` now allows `final` up to 13.00 and continues to leave `difficulty_body`/`difficulty_apparatus` uncapped.

- [ ] **Step 1: Write the failing tests**

Append to `backend/test/test_models/test_judge_score.py`:

```python
def test_judge_final_score_up_to_13_allowed(db_session):
    # Levels 1-3 hand the scorer one finished mark out of 13 (D and E already folded
    # in on paper), so Panel.final is capped at 13 rather than execution's 10.
    routine = make_routine(db_session)
    judge = make_judge(db_session)
    judge_score = JudgeScore(
        routine_id=routine.id,
        judge_id=judge.id,
        value=13.00,
        panel=Panel.final,
    )
    db_session.add(judge_score)
    db_session.commit()

    assert judge_score.id is not None


def test_judge_final_score_above_13_not_allowed(db_session):
    routine = make_routine(db_session)
    judge = make_judge(db_session)
    judge_score = JudgeScore(
        routine_id=routine.id,
        judge_id=judge.id,
        value=13.05,
        panel=Panel.final,
    )
    db_session.add(judge_score)

    with pytest.raises(IntegrityError):
        db_session.commit()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest test/test_models/test_judge_score.py -k final -v`
Expected: FAIL — `AttributeError: final` (the `Panel` enum has no such member).

- [ ] **Step 3: Add the enum member and update the cap constraint**

In `backend/app/models.py`, extend the `Panel` enum:

```python
class Panel(StrEnum):
    # Difficulty is split into two independently-judged subgroups per FIG's Code of
    # Points (DB: Difficulty of Body, DA: Difficulty of Apparatus) -- their scores are
    # summed, not averaged together, and neither is capped at 10 like artistry/execution.
    difficulty_body = "difficulty_body"
    difficulty_apparatus = "difficulty_apparatus"
    execution = "execution"
    artistry = "artistry"
    # Levels 1-3 only: the judges fold D and E together on paper and hand the scorer a
    # single finished mark out of 13. This is neither an execution score nor a
    # difficulty score, so it gets its own panel -- storing it as `execution` with the
    # cap raised to 13 would weaken a real invariant (E is out of 10 at EVERY level)
    # for the sake of a different quantity wearing E's name.
    final = "final"
```

Replace the `ck_judge_score_panel_value_cap` constraint in `JudgeScore.__table_args__`:

```python
        CheckConstraint(
            "CASE panel "
            "WHEN 'difficulty_body' THEN true "
            "WHEN 'difficulty_apparatus' THEN true "
            "WHEN 'final' THEN value <= 13 "
            "ELSE value <= 10 END",
            name="ck_judge_score_panel_value_cap",
        ),
```

- [ ] **Step 4: Write the migration**

Create `backend/migrations/versions/c1a7e4b90f22_add_final_panel_for_levels_1_3.py`:

```python
"""add_final_panel_for_levels_1_3

Revision ID: c1a7e4b90f22
Revises: b3f1c9d47e20
Create Date: 2026-07-20 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1a7e4b90f22"
down_revision: str | Sequence[str] | None = "b3f1c9d47e20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_CAP = "panel IN ('difficulty_body', 'difficulty_apparatus') OR value <= 10"
_NEW_CAP = (
    "CASE panel "
    "WHEN 'difficulty_body' THEN true "
    "WHEN 'difficulty_apparatus' THEN true "
    "WHEN 'final' THEN value <= 13 "
    "ELSE value <= 10 END"
)


def upgrade() -> None:
    """Upgrade schema."""
    # Autogenerate never sees a new enum value (see CLAUDE.md), so this is hand-written.
    # The extra wrinkle: Postgres refuses to *use* an enum value in the same transaction
    # that added it, and the CHECK constraint below references the literal 'final'.
    # autocommit_block() commits the ALTER TYPE in its own transaction first.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE panel ADD VALUE IF NOT EXISTS 'final'")

    op.drop_constraint("ck_judge_score_panel_value_cap", "judge_scores", type_="check")
    op.create_check_constraint("ck_judge_score_panel_value_cap", "judge_scores", _NEW_CAP)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the constraint BEFORE rebuilding the type: it references 'final', which the
    # rebuilt type will not have.
    op.drop_constraint("ck_judge_score_panel_value_cap", "judge_scores", type_="check")

    # Postgres cannot remove a value from an enum -- the type must be rebuilt. This
    # fails loudly if any judge_scores row still sits on 'final', which is correct:
    # such a row has no representation in the old schema.
    op.execute("ALTER TYPE panel RENAME TO panel_old")
    op.execute(
        "CREATE TYPE panel AS ENUM "
        "('difficulty_body', 'difficulty_apparatus', 'execution', 'artistry')"
    )
    op.execute(
        "ALTER TABLE judge_scores ALTER COLUMN panel TYPE panel USING panel::text::panel"
    )
    op.execute("DROP TYPE panel_old")

    op.create_check_constraint("ck_judge_score_panel_value_cap", "judge_scores", _OLD_CAP)
```

- [ ] **Step 5: Apply the migration and run the tests**

Run from the repo root: `make dev`
Then: `cd backend && pytest test/test_models/test_judge_score.py -v`
Expected: PASS — including the two new tests and all pre-existing ones (the `execution` value-out-of-range and `difficulty_*` uncapped tests must still pass; they exercise the `ELSE`/`WHEN` arms of the new CASE).

- [ ] **Step 6: Verify the downgrade round-trips**

Run from `backend/`: `alembic downgrade -1 && alembic upgrade head`
Expected: both complete without error.

- [ ] **Step 7: Regenerate the OpenAPI types**

Run from the repo root: `make types`
Expected: `frontend/src/api/schema.d.ts` gains `"final"` in the `Panel` enum union.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models.py backend/migrations/versions/c1a7e4b90f22_add_final_panel_for_levels_1_3.py backend/test/test_models/test_judge_score.py frontend/src/api/schema.d.ts
git commit -m "feat: add Panel.final for the levels 1-3 pre-aggregated mark"
```

---

### Task 2: The band→profile table replaces `E_ONLY_LEVELS`

The spec's core architectural decision: one declarative table, five consumers. This task builds the table and rewires panel validity (the first consumer); later tasks consume the same table for math, medals, and UI.

**Files:**
- Modify: `backend/app/scoring.py:19-39` (delete `E_ONLY_LEVELS`, rewrite `is_panel_valid_for_level`)
- Modify: `backend/app/routers/judge_score.py:26-56` (docstring + 422 message)
- Test: `backend/test/test_scoring.py:201-212`, `backend/test/test_routers/test_judge_score_router.py`

**Interfaces:**
- Consumes: `Panel.final` from Task 1.
- Produces:
  - `MedalMode` (`StrEnum`: `cutoff`, `placement`)
  - `ScoringProfile` — frozen dataclass with fields `band: str`, `panels: frozenset[Panel]`, `judges_per_panel: Mapping[Panel, int]`, `medal_mode: MedalMode`, `tie_break_on_execution: bool`
  - `BAND_1_3`, `BAND_4_7`, `BAND_8_PLUS` — the three `ScoringProfile` instances
  - `profile_for_level(level: Level) -> ScoringProfile`
  - `is_panel_valid_for_level(level: Level, panel: Panel) -> bool` (unchanged signature, new behaviour)

- [ ] **Step 1: Write the failing tests**

In `backend/test/test_scoring.py`, **replace** `test_is_panel_valid_for_level_e_only_levels` and `test_is_panel_valid_for_level_non_gated_levels` (lines 201–212) with:

```python
@pytest.mark.parametrize(
    "level, valid_panels",
    [
        (Level.level_1, {Panel.final}),
        (Level.level_3, {Panel.final}),
        (Level.level_4, {Panel.difficulty_body, Panel.execution}),
        (Level.level_7, {Panel.difficulty_body, Panel.execution}),
        (
            Level.level_8,
            {
                Panel.difficulty_body,
                Panel.difficulty_apparatus,
                Panel.artistry,
                Panel.execution,
            },
        ),
        (
            Level.senior,
            {
                Panel.difficulty_body,
                Panel.difficulty_apparatus,
                Panel.artistry,
                Panel.execution,
            },
        ),
    ],
)
@pytest.mark.parametrize("panel", list(Panel))
def test_is_panel_valid_for_level(level, valid_panels, panel):
    assert is_panel_valid_for_level(level, panel) == (panel in valid_panels)


@pytest.mark.parametrize("level", list(Level))
def test_every_level_has_a_scoring_profile(level):
    # The map is built exhaustively rather than with a default, so a Level added to the
    # enum without a band assignment fails here instead of silently scoring as 8+.
    assert profile_for_level(level) in (BAND_1_3, BAND_4_7, BAND_8_PLUS)


def test_band_profiles_match_the_spec():
    assert BAND_1_3.medal_mode is MedalMode.cutoff
    assert BAND_1_3.tie_break_on_execution is False
    assert BAND_1_3.judges_per_panel == {Panel.final: 1}

    assert BAND_4_7.medal_mode is MedalMode.placement
    assert BAND_4_7.tie_break_on_execution is False
    # Deliberate asymmetry (spec, confirmed 2026-07-20): TWO DB judges here, but one DB
    # and one DA at 8+. Do not "fix" this into consistency.
    assert BAND_4_7.judges_per_panel == {Panel.difficulty_body: 2, Panel.execution: 2}

    assert BAND_8_PLUS.medal_mode is MedalMode.placement
    assert BAND_8_PLUS.tie_break_on_execution is True
    assert BAND_8_PLUS.judges_per_panel == {
        Panel.difficulty_body: 1,
        Panel.difficulty_apparatus: 1,
        Panel.artistry: 2,
        Panel.execution: 4,
    }
```

Update the import block at the top of `backend/test/test_scoring.py` to add the new names:

```python
from app.scoring import (
    BAND_1_3,
    BAND_4_7,
    BAND_8_PLUS,
    AllAroundStanding,
    ApparatusStanding,
    MedalMode,
    RoutineScoreResult,
    compute_routine_score,
    is_panel_valid_for_level,
    medal_for_total,
    profile_for_level,
    rank_all_around,
    rank_apparatus,
    trimmed_mean,
)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest test/test_scoring.py -v`
Expected: FAIL at collection — `ImportError: cannot import name 'BAND_1_3' from 'app.scoring'`.

- [ ] **Step 3: Build the profile table**

In `backend/app/scoring.py`, **replace** the `E_ONLY_LEVELS` block and `is_panel_valid_for_level` (lines 19–39) with:

```python
class MedalMode(StrEnum):
    """How a band decides who gets a medal (spec: "Two medal systems")."""

    cutoff = "cutoff"  # levels 1-3: Meet.medal_gold_min/medal_silver_min, on the all-around
    placement = "placement"  # levels 4+: the first three distinct RANKS


@dataclass(frozen=True)
class ScoringProfile:
    """
    Everything that varies between the three FIG scoring bands, in one place.

    This rule is needed in at least five places (backend panel validity, backend math,
    the frontend math mirror, the judge-slot panel UI, and the score form's box
    layout). Specifying it once and deriving downward is deliberate: the previous
    two-band rule was implemented independently in several of those places and drifted.

    `judges_per_panel` is the expected panel size, used by the UI to lay out score
    boxes and to decide which judge slots are required. It is not enforced at the API:
    a routine with a missing mark is incomplete, not invalid.
    """

    band: str
    panels: frozenset[Panel]
    judges_per_panel: Mapping[Panel, int]
    medal_mode: MedalMode
    tie_break_on_execution: bool


# Levels 1-3: the judges compute D+E on paper and hand the scorer one finished mark out
# of 13. From the scorer's point of view there is exactly ONE judge, so nothing is
# averaged -- the entered mark IS the routine's total.
BAND_1_3 = ScoringProfile(
    band="1-3",
    panels=frozenset({Panel.final}),
    judges_per_panel={Panel.final: 1},
    medal_mode=MedalMode.cutoff,
    tie_break_on_execution=False,
)

# Levels 4-7: two judges both score Difficulty of Body (there is no DA at this band)
# and two score Execution. D is out of 3 (13 - 10) but is deliberately NOT tracked or
# constrained -- a judge's D mark cannot exceed 3 in practice.
BAND_4_7 = ScoringProfile(
    band="4-7",
    panels=frozenset({Panel.difficulty_body, Panel.execution}),
    judges_per_panel={Panel.difficulty_body: 2, Panel.execution: 2},
    medal_mode=MedalMode.placement,
    tie_break_on_execution=False,
)

# Levels 8+: the full FIG panel. Note the deliberate asymmetry with 4-7 -- one DB judge
# and one DA judge here, versus two DB judges there (confirmed 2026-07-20).
BAND_8_PLUS = ScoringProfile(
    band="8+",
    panels=frozenset(
        {Panel.difficulty_body, Panel.difficulty_apparatus, Panel.artistry, Panel.execution}
    ),
    judges_per_panel={
        Panel.difficulty_body: 1,
        Panel.difficulty_apparatus: 1,
        Panel.artistry: 2,
        Panel.execution: 4,
    },
    medal_mode=MedalMode.placement,
    tie_break_on_execution=True,
)

_BAND_1_3_LEVELS = (Level.level_1, Level.level_2, Level.level_3)
_BAND_4_7_LEVELS = (Level.level_4, Level.level_5, Level.level_6, Level.level_7)

# Built exhaustively over Level rather than with a `.get(level, BAND_8_PLUS)` default:
# a level added to the enum without a band assignment should fail loudly in the tests,
# not silently acquire the full FIG panel.
_PROFILE_BY_LEVEL: dict[Level, ScoringProfile] = {
    **{level: BAND_1_3 for level in _BAND_1_3_LEVELS},
    **{level: BAND_4_7 for level in _BAND_4_7_LEVELS},
    **{
        level: BAND_8_PLUS
        for level in Level
        if level not in (*_BAND_1_3_LEVELS, *_BAND_4_7_LEVELS)
    },
}


def profile_for_level(level: Level) -> ScoringProfile:
    """The scoring profile governing `level`. See ScoringProfile."""
    return _PROFILE_BY_LEVEL[level]


def is_panel_valid_for_level(level: Level, panel: Panel) -> bool:
    """Whether a judge score on `panel` is valid for a routine at `level`."""
    return panel in profile_for_level(level).panels
```

Update the imports at the top of `backend/app/scoring.py`:

```python
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Literal

from app.models import Level, MeetEntry, Panel, Routine
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest test/test_scoring.py -v`
Expected: PASS.

- [ ] **Step 5: Update the judge-score router's docstring and message**

In `backend/app/routers/judge_score.py`, replace the first bullet of the `create_judge_score` docstring:

```python
    - Which panels are legal depends on the routine's level band (see
      app.scoring.profile_for_level): levels 1-3 accept only `final`, levels 4-7 accept
      `difficulty_body` and `execution`, levels 8+ accept the full D/A/E set. A mark on
      a panel outside that set is rejected with a 422, since the payload is invalid for
      that routine's level, not merely in conflict with existing data.
```

Replace the 422 raise (lines 49–56):

```python
    if not is_panel_valid_for_level(routine.entry.level, payload.panel):
        profile = profile_for_level(routine.entry.level)
        valid = ", ".join(sorted(panel.value for panel in profile.panels))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Routine {payload.routine_id} is level {routine.entry.level.value} "
                f"(scoring band {profile.band}), which is scored on {valid} -- "
                f"{payload.panel.value} is not valid."
            ),
        )
```

Update the import on line 18:

```python
from app.scoring import is_panel_valid_for_level, profile_for_level
```

- [ ] **Step 6: Add router tests for the new gate**

Append to `backend/test/test_routers/test_judge_score_router.py` (match the file's existing fixture/helper style for building a routine at a given level):

```python
def test_create_judge_score_rejects_execution_at_level_1(client, db_session):
    # Levels 1-3 record ONE pre-aggregated mark on Panel.final. An execution mark is
    # now invalid there -- this is the band that changed most from the old rule.
    entry = make_meet_entry(
        db_session,
        meet=make_meet(db_session),
        gymnast=make_gymnast(db_session),
        level=Level.level_1,
    )
    routine = make_routine(db_session, meet_entry=entry)
    judge = make_judge(db_session)
    db_session.commit()

    response = client.post(
        "/judge-scores/",
        json={
            "routine_id": routine.id,
            "judge_id": judge.id,
            "panel": "execution",
            "value": "9.00",
        },
    )

    assert response.status_code == 422
    assert "final" in response.json()["detail"]


def test_create_judge_score_accepts_final_at_level_1(client, db_session):
    entry = make_meet_entry(
        db_session,
        meet=make_meet(db_session),
        gymnast=make_gymnast(db_session),
        level=Level.level_1,
    )
    routine = make_routine(db_session, meet_entry=entry)
    judge = make_judge(db_session)
    db_session.commit()

    response = client.post(
        "/judge-scores/",
        json={
            "routine_id": routine.id,
            "judge_id": judge.id,
            "panel": "final",
            "value": "11.50",
        },
    )

    assert response.status_code == 201


def test_create_judge_score_accepts_difficulty_body_at_level_4(client, db_session):
    # The headline spec change: the backend used to REJECT a Difficulty mark at level 4.
    entry = make_meet_entry(
        db_session,
        meet=make_meet(db_session),
        gymnast=make_gymnast(db_session),
        level=Level.level_4,
    )
    routine = make_routine(db_session, meet_entry=entry)
    judge = make_judge(db_session)
    db_session.commit()

    response = client.post(
        "/judge-scores/",
        json={
            "routine_id": routine.id,
            "judge_id": judge.id,
            "panel": "difficulty_body",
            "value": "2.40",
        },
    )

    assert response.status_code == 201


def test_create_judge_score_rejects_artistry_at_level_4(client, db_session):
    entry = make_meet_entry(
        db_session,
        meet=make_meet(db_session),
        gymnast=make_gymnast(db_session),
        level=Level.level_4,
    )
    routine = make_routine(db_session, meet_entry=entry)
    judge = make_judge(db_session)
    db_session.commit()

    response = client.post(
        "/judge-scores/",
        json={
            "routine_id": routine.id,
            "judge_id": judge.id,
            "panel": "artistry",
            "value": "8.00",
        },
    )

    assert response.status_code == 422


def test_create_judge_score_rejects_final_at_level_8(client, db_session):
    entry = make_meet_entry(
        db_session,
        meet=make_meet(db_session),
        gymnast=make_gymnast(db_session),
        level=Level.level_8,
    )
    routine = make_routine(db_session, meet_entry=entry)
    judge = make_judge(db_session)
    db_session.commit()

    response = client.post(
        "/judge-scores/",
        json={
            "routine_id": routine.id,
            "judge_id": judge.id,
            "panel": "final",
            "value": "12.00",
        },
    )

    assert response.status_code == 422
```

Ensure the file's imports include `Level` from `app.models` and the `make_meet_entry` / `make_meet` / `make_gymnast` / `make_routine` / `make_judge` factories from `test.conftest` (follow the file's existing import style).

- [ ] **Step 7: Run the full backend suite**

Run from the repo root: `make test`
Expected: PASS. If a pre-existing test asserts that a difficulty mark at level 4 is rejected, update it to the new rule — that assertion encodes the superseded spec.

- [ ] **Step 8: Lint and commit**

```bash
cd backend && ruff check . && ruff format .
git add backend/app/scoring.py backend/app/routers/judge_score.py backend/test/test_scoring.py backend/test/test_routers/test_judge_score_router.py
git commit -m "feat: replace E_ONLY_LEVELS with the three-band scoring profile table"
```

---

### Task 3: `compute_routine_score` and ranking become band-aware

Two behaviour changes: levels 1–3 total from the `final` mark, and the E tie-break applies only at 8+.

**Files:**
- Modify: `backend/app/scoring.py` (`RoutineScoreResult`, `compute_routine_score`, `rank_apparatus`, `rank_all_around`)
- Test: `backend/test/test_scoring.py`

**Interfaces:**
- Consumes: `profile_for_level`, `BAND_1_3` from Task 2.
- Produces: `RoutineScoreResult` gains a `final_score: Decimal` field (0 outside levels 1–3). `compute_routine_score(routine)` keeps its signature but now reads `routine.entry.level`. `rank_apparatus`/`rank_all_around` signatures unchanged.

- [ ] **Step 1: Update the test helpers to carry a level**

In `backend/test/test_scoring.py`, replace `_routine` (lines 74–75) and `_entry` (lines 215–216):

```python
def _routine(marks, penalty="0", level=Level.senior):
    # Defaults to a level-8+ band so the pre-existing full-FIG worked examples below
    # keep exercising the (DB + DA) + A + E path unchanged.
    return SimpleNamespace(
        judge_scores=marks,
        penalty=Decimal(penalty),
        entry=SimpleNamespace(level=level),
    )
```

```python
def _entry(routines, level=Level.senior):
    return SimpleNamespace(routines=routines, level=level)
```

- [ ] **Step 2: Write the failing tests**

Append to `backend/test/test_scoring.py`:

```python
def test_compute_routine_score_level_1_3_records_the_final_mark():
    # The application is not calculating a score at this band; it is recording one.
    routine = _routine([_mark(Panel.final, "11.75")], level=Level.level_2)

    result = compute_routine_score(routine)

    assert result.final_score == Decimal("11.75")
    assert result.total == Decimal("11.75")
    assert result.d_score == Decimal("0")
    assert result.a_score == Decimal("0")
    assert result.e_score == Decimal("0")


def test_compute_routine_score_level_1_3_subtracts_penalty():
    routine = _routine([_mark(Panel.final, "12.00")], penalty="0.30", level=Level.level_3)

    result = compute_routine_score(routine)

    assert result.total == Decimal("11.70")


def test_compute_routine_score_level_1_3_ignores_marks_on_other_panels():
    # Stale/illegal marks (direct ORM writes bypass the API's panel gate) must not leak
    # into a band-1-3 total.
    routine = _routine(
        [_mark(Panel.final, "10.00"), _mark(Panel.execution, "9.00")],
        level=Level.level_1,
    )

    result = compute_routine_score(routine)

    assert result.e_score == Decimal("0")
    assert result.total == Decimal("10.00")


def test_compute_routine_score_level_4_7_averages_the_two_db_marks():
    # No DA exists at this band, so trimmed_mean([]) returns 0 and the shipped additive
    # formula (DB + DA) already yields avg(DB1, DB2). Adding zero is a no-op.
    routine = _routine(
        [
            _mark(Panel.difficulty_body, "2.40"),
            _mark(Panel.difficulty_body, "2.60"),
            _mark(Panel.execution, "8.50"),
            _mark(Panel.execution, "8.70"),
        ],
        level=Level.level_5,
    )

    result = compute_routine_score(routine)

    assert result.d_score == Decimal("2.50")
    assert result.e_score == Decimal("8.60")
    assert result.final_score == Decimal("0")
    assert result.total == Decimal("11.10")


def test_compute_routine_score_8_plus_is_unchanged_and_has_zero_final():
    routine = _routine(
        [
            _mark(Panel.difficulty_body, "5.00"),
            _mark(Panel.difficulty_apparatus, "3.00"),
            _mark(Panel.artistry, "8.00"),
            _mark(Panel.execution, "9.00"),
        ]
    )

    result = compute_routine_score(routine)

    assert result.final_score == Decimal("0")
    assert result.total == Decimal("25.00")


def test_rank_apparatus_breaks_ties_on_execution_at_level_8_plus():
    lower_e = _routine(
        [_mark(Panel.difficulty_body, "6.00"), _mark(Panel.execution, "8.00")]
    )
    higher_e = _routine(
        [_mark(Panel.difficulty_body, "5.00"), _mark(Panel.execution, "9.00")]
    )

    standings = rank_apparatus([lower_e, higher_e])

    assert [standing.routine for standing in standings] == [higher_e, lower_e]
    assert [standing.rank for standing in standings] == [1, 2]


def test_rank_apparatus_does_not_break_ties_on_execution_at_levels_4_7():
    # Spec: no tie-breaks below level 8. Equal totals share a rank even when their
    # Execution differs.
    lower_e = _routine(
        [_mark(Panel.difficulty_body, "3.00"), _mark(Panel.execution, "8.00")],
        level=Level.level_5,
    )
    higher_e = _routine(
        [_mark(Panel.difficulty_body, "2.00"), _mark(Panel.execution, "9.00")],
        level=Level.level_5,
    )

    standings = rank_apparatus([lower_e, higher_e])

    assert [standing.rank for standing in standings] == [1, 1]


def test_rank_all_around_does_not_break_ties_on_execution_at_levels_1_3():
    a = _entry([_routine([_mark(Panel.final, "12.00")], level=Level.level_1)], level=Level.level_1)
    b = _entry([_routine([_mark(Panel.final, "12.00")], level=Level.level_1)], level=Level.level_1)

    standings = rank_all_around([a, b])

    assert [standing.rank for standing in standings] == [1, 1]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && pytest test/test_scoring.py -v`
Expected: FAIL — `AttributeError: 'RoutineScoreResult' object has no attribute 'final_score'`.

- [ ] **Step 4: Implement the band-aware computation**

In `backend/app/scoring.py`, replace `RoutineScoreResult` and `compute_routine_score`:

```python
@dataclass(frozen=True)
class RoutineScoreResult:
    d_score: Decimal
    a_score: Decimal
    e_score: Decimal
    final_score: Decimal
    penalty: Decimal
    total: Decimal


def compute_routine_score(routine) -> RoutineScoreResult:
    """
    Compute a routine's panel scores and total from its raw JudgeScore marks, according
    to the scoring band of its entry's level (see ScoringProfile).

    Args:
        routine: A Routine ORM instance. Its `judge_scores` are grouped by panel and
        reduced via `trimmed_mean`; a panel with no marks yet contributes 0. The band is
        read from `routine.entry.level`.

    Returns:
        RoutineScoreResult: the per-panel scores, penalty, and total, each rounded to
        2 decimal places to match the Numeric(6, 2) DB columns.

    Bands:
    - Levels 1-3 are pre-aggregated: one `final` mark out of 13 IS the routine score,
      less penalty. D/A/E are forced to 0 so a stale mark on another panel (direct ORM
      writes bypass the API's panel gate) cannot leak into the total.
    - Levels 4-7 and 8+ share one formula. Per FIG's Code of Points, D is the *sum* of
      two independently-judged subgroups (difficulty_body + difficulty_apparatus), not a
      trimmed mean of a single pool like artistry/execution. At 4-7 there is no DA, so
      `trimmed_mean([])` returns 0 and the sum reduces to the required average of the
      two DB marks -- adding zero is a no-op, which is why this band needs no branch.
    """
    by_panel: dict[Panel, list[Decimal]] = {panel: [] for panel in Panel}
    for judge_score in routine.judge_scores:
        by_panel[judge_score.panel].append(judge_score.value)

    def rounded(values: list[Decimal]) -> Decimal:
        return trimmed_mean(values).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def quantized(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    penalty = routine.penalty
    profile = profile_for_level(routine.entry.level)

    if profile is BAND_1_3:
        final_score = rounded(by_panel[Panel.final])
        return RoutineScoreResult(
            d_score=Decimal("0.00"),
            a_score=Decimal("0.00"),
            e_score=Decimal("0.00"),
            final_score=final_score,
            penalty=penalty,
            total=quantized(final_score - penalty),
        )

    db_score = rounded(by_panel[Panel.difficulty_body])
    da_score = rounded(by_panel[Panel.difficulty_apparatus])
    d_score = db_score + da_score
    a_score = rounded(by_panel[Panel.artistry])
    e_score = rounded(by_panel[Panel.execution])

    return RoutineScoreResult(
        d_score=d_score,
        a_score=a_score,
        e_score=e_score,
        final_score=Decimal("0.00"),
        penalty=penalty,
        total=quantized(d_score + a_score + e_score - penalty),
    )
```

- [ ] **Step 5: Make the tie-break band-dependent**

In `backend/app/scoring.py`, replace `rank_apparatus` and `rank_all_around`:

```python
def _tie_break_key(level: Level, e_value: Decimal) -> Decimal:
    """
    The Execution component of a sort key, zeroed for bands that do not tie-break.

    Per FIG Technical Regulations, ties break on highest total Execution -- but only at
    levels 8+ (spec: "Tie-breaking by band"). Returning 0 for the other bands makes
    equal totals compare equal, so they share a rank via _assign_ranks. Computed per
    row rather than per call so a caller that did not filter to a single level still
    gets each row's own rule applied.
    """
    return e_value if profile_for_level(level).tie_break_on_execution else Decimal("0")


def rank_apparatus(routines) -> list[ApparatusStanding]:
    """
    Rank routines within a single apparatus category (caller filters to one
    (meet, level, age_group, apparatus) slice first).

    Ties break by total score first, then -- at levels 8+ only -- by highest total
    Execution. A routine still tied on both shares its rank with the next (competition
    ranking, see _assign_ranks).
    """
    scored = [(routine, compute_routine_score(routine)) for routine in routines]

    def sort_key(pair):
        routine, score = pair
        return (score.total, _tie_break_key(routine.entry.level, score.e_score))

    scored.sort(key=sort_key, reverse=True)

    ranks = _assign_ranks(scored, key_fn=sort_key)
    return [
        ApparatusStanding(rank=rank, routine=routine, score=score)
        for rank, (routine, score) in zip(ranks, scored, strict=True)
    ]


def rank_all_around(entries) -> list[AllAroundStanding]:
    """
    Rank meet entries by the sum of their routines' totals (the all-around), within a
    single (meet, level, age_group) slice (caller filters first).

    A competitor with an incomplete apparatus set (e.g. injured mid-meet) is still ranked
    on their partial sum, not excluded -- `routines_counted` lets the caller surface that
    the total is partial, matching how compute_routine_score returns 0 for missing panels
    rather than erroring. Same tie-break as rank_apparatus: total, then summed Execution
    at levels 8+ only, then shared rank.
    """
    summed = []
    for entry in entries:
        results = [compute_routine_score(routine) for routine in entry.routines]
        total = sum((result.total for result in results), Decimal("0"))
        e_total = sum((result.e_score for result in results), Decimal("0"))
        summed.append((entry, total, e_total, len(results)))

    def sort_key(row):
        entry, total, e_total, _count = row
        return (total, _tie_break_key(entry.level, e_total))

    summed.sort(key=sort_key, reverse=True)

    ranks = _assign_ranks(summed, key_fn=sort_key)
    return [
        AllAroundStanding(
            rank=rank, entry=entry, total=total, e_total=e_total, routines_counted=count
        )
        for rank, (entry, total, e_total, count) in zip(ranks, summed, strict=True)
    ]
```

- [ ] **Step 6: Run the tests to verify they pass**

Run from the repo root: `make test`
Expected: PASS. Any pre-existing test constructing a `RoutineScoreResult` positionally must gain `final_score` — fix those at the call site.

- [ ] **Step 7: Lint and commit**

```bash
cd backend && ruff check . && ruff format .
git add backend/app/scoring.py backend/test/test_scoring.py
git commit -m "feat: make routine scoring and tie-breaks band-aware"
```

---

### Task 4: Placement medals

Levels 4+ award medals by placement over the first three **distinct ranks**; levels 1–3 keep the score cutoffs.

**Files:**
- Modify: `backend/app/scoring.py` (add `assign_placement_medals`)
- Modify: `backend/app/routers/results.py` (module docstring, both endpoints)
- Test: `backend/test/test_scoring.py`, `backend/test/test_routers/test_results_router.py`

**Interfaces:**
- Consumes: `profile_for_level`, `MedalMode` (Task 2); `rank_apparatus`/`rank_all_around` (Task 3).
- Produces: `assign_placement_medals(ranks: Sequence[int]) -> list[Medal | None]` — one medal (or `None`) per input rank, in input order.

- [ ] **Step 1: Write the failing tests**

Append to `backend/test/test_scoring.py`:

```python
@pytest.mark.parametrize(
    "ranks, expected",
    [
        ([1, 2, 3, 4], ["gold", "silver", "bronze", None]),
        # Two tied at top: distinct ranks are 1, 3, 4 -> two golds, then silver, bronze.
        ([1, 1, 3, 4], ["gold", "gold", "silver", "bronze"]),
        # One winner, two tied second: distinct ranks 1, 2, 4 -> the 4th-place gymnast
        # still takes bronze. A `rank <= 3` implementation would deny it.
        ([1, 2, 2, 4], ["gold", "silver", "silver", "bronze"]),
        ([1, 1, 1, 4], ["gold", "gold", "gold", "silver"]),
        ([1, 2], ["gold", "silver"]),
        ([], []),
    ],
)
def test_assign_placement_medals(ranks, expected):
    assert assign_placement_medals(ranks) == expected
```

Add `assign_placement_medals` to the `from app.scoring import (...)` block.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest test/test_scoring.py -k placement -v`
Expected: FAIL at collection — `ImportError: cannot import name 'assign_placement_medals'`.

- [ ] **Step 3: Implement `assign_placement_medals`**

Add to `backend/app/scoring.py`, immediately after `medal_for_total`:

```python
def assign_placement_medals(ranks: Sequence[int]) -> list[Medal | None]:
    """
    Placement medals for levels 4+: the first three DISTINCT rank values take gold,
    silver and bronze, and everyone sharing a rank shares its medal.

    Deliberately a separate pass over ranks rather than a `rank <= 3` lookup: with one
    winner and two tied for second the ranks are 1, 2, 2, 4, and `rank <= 3` would deny
    bronze to the fourth competitor who has in fact placed third.

    Expressed over ranks rather than over distinct totals on purpose. The two agree
    until level 8+, where the Execution tie-break separates equal totals into different
    ranks -- ranks compose with tie-breaking, totals fight it.

    Args:
        ranks: competition ranks (1,2,2,4), in the order rows will be returned.

    Returns:
        One medal or None per input rank, in the same order.
    """
    podium = sorted(set(ranks))[:3]
    tiers: tuple[Medal, ...] = ("gold", "silver", "bronze")
    by_rank: dict[int, Medal] = dict(zip(podium, tiers, strict=False))
    return [by_rank.get(rank) for rank in ranks]
```

Add `Sequence` to the imports:

```python
from collections.abc import Mapping, Sequence
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest test/test_scoring.py -k placement -v`
Expected: PASS.

- [ ] **Step 5: Apply the per-band medal mode in the results router**

In `backend/app/routers/results.py`, replace the `medal` bullet of the module docstring:

```
- `medal` on each row is additive to `rank`, and which system produces it depends on the
  row's level band (app/scoring.py):
  - **Levels 1-3** use the meet's configured `medal_gold_min`/`medal_silver_min` score
    cutoffs, answering "did this total clear a threshold". Those cutoffs are scaled for
    the levels 1-3 ALL-AROUND (2 apparatus, max 26), so they are meaningful on
    /all-around and only incidentally applied per-apparatus. Both cutoffs null (the
    default) means the meet isn't using them, so those rows' `medal` is null.
  - **Levels 4+** use placement: the first three distinct ranks, ties sharing a medal
    (see `assign_placement_medals`). No configuration needed.
  Placement medals are assigned over the rankings actually returned, so -- exactly like
  `rank` itself -- they are only meaningful when the caller has filtered to a single
  (level, age_group) slice.
```

Replace the import on line 42:

```python
from app.scoring import (
    Medal,
    MedalMode,
    assign_placement_medals,
    medal_for_total,
    profile_for_level,
    rank_all_around,
    rank_apparatus,
)
```

Add `from decimal import Decimal` to the stdlib import block at the top of the file (it currently imports only `Annotated` from `typing`).

Add a helper after `_competitor_name`:

```python
def _medal_for(
    level: Level, total: Decimal, placement: Medal | None, meet: Meet
) -> Medal | None:
    """Cutoffs at levels 1-3, placement at 4+ -- see the module docstring."""
    if profile_for_level(level).medal_mode is MedalMode.cutoff:
        return medal_for_total(total, meet.medal_gold_min, meet.medal_silver_min)
    return placement
```

In `get_apparatus_standings`, after `standings = rank_apparatus(query.all())`:

```python
    placements = assign_placement_medals([standing.rank for standing in standings])
```

and replace the `medal=` argument inside the `ApparatusStandingRow(...)` comprehension, changing the comprehension to enumerate:

```python
        rankings=[
            ApparatusStandingRow(
                rank=standing.rank,
                entry_id=standing.routine.entry_id,
                routine_id=standing.routine.id,
                competitor_name=_competitor_name(standing.routine.entry),
                bib_number=standing.routine.entry.bib_number,
                level=standing.routine.entry.level,
                age_group=standing.routine.entry.age_group,
                apparatus=standing.routine.apparatus,
                d_score=standing.score.d_score,
                a_score=standing.score.a_score,
                e_score=standing.score.e_score,
                penalty=standing.score.penalty,
                total=standing.score.total,
                medal=_medal_for(
                    standing.routine.entry.level,
                    standing.score.total,
                    placements[index],
                    meet,
                ),
            )
            for index, standing in enumerate(standings)
        ],
```

Apply the same change in `get_all_around_standings`:

```python
    placements = assign_placement_medals([standing.rank for standing in standings])
```

```python
        rankings=[
            AllAroundStandingRow(
                rank=standing.rank,
                entry_id=standing.entry.id,
                competitor_name=_competitor_name(standing.entry),
                bib_number=standing.entry.bib_number,
                level=standing.entry.level,
                age_group=standing.entry.age_group,
                total=standing.total,
                e_total=standing.e_total,
                routines_counted=standing.routines_counted,
                medal=_medal_for(
                    standing.entry.level, standing.total, placements[index], meet
                ),
            )
            for index, standing in enumerate(standings)
        ],
```

- [ ] **Step 6: Add router tests for both medal systems**

Append to `backend/test/test_routers/test_results_router.py` (match the file's existing helper style for creating entries, routines and scores):

```python
def test_all_around_uses_cutoff_medals_at_levels_1_3(client, db_session):
    meet = make_meet(
        db_session, medal_gold_min=Decimal("24.00"), medal_silver_min=Decimal("21.00")
    )
    for total in ("13.00", "11.00"):
        entry = make_meet_entry(
            db_session, meet=meet, gymnast=make_gymnast(db_session), level=Level.level_1
        )
        for apparatus in (Apparatus.hoop, Apparatus.ball):
            routine = make_routine(db_session, meet_entry=entry, apparatus=apparatus)
            make_judge_score(
                db_session,
                routine=routine,
                judge=make_judge(db_session, first_name=f"J{apparatus}{total}"),
                panel=Panel.final,
                value=Decimal(total),
            )
    db_session.commit()

    response = client.get(f"/meets/{meet.id}/all-around", params={"level": "level_1"})

    assert response.status_code == 200
    rows = response.json()["rankings"]
    # 26.00 clears the 24.00 gold cutoff; 22.00 lands between silver and gold.
    assert [row["total"] for row in rows] == ["26.00", "22.00"]
    assert [row["medal"] for row in rows] == ["gold", "silver"]


def test_standings_use_placement_medals_at_level_8(client, db_session):
    # No cutoffs configured at all: placement medals need no configuration.
    meet = make_meet(db_session)
    for value in ("9.00", "8.00", "7.00", "6.00"):
        entry = make_meet_entry(
            db_session, meet=meet, gymnast=make_gymnast(db_session), level=Level.level_8
        )
        routine = make_routine(db_session, meet_entry=entry, apparatus=Apparatus.hoop)
        make_judge_score(
            db_session,
            routine=routine,
            judge=make_judge(db_session, first_name=f"J{value}"),
            panel=Panel.execution,
            value=Decimal(value),
        )
    db_session.commit()

    response = client.get(
        f"/meets/{meet.id}/standings",
        params={"apparatus": "hoop", "level": "level_8"},
    )

    assert response.status_code == 200
    rows = response.json()["rankings"]
    assert [row["rank"] for row in rows] == [1, 2, 3, 4]
    assert [row["medal"] for row in rows] == ["gold", "silver", "bronze", None]


def test_standings_placement_medals_share_a_rank_and_still_award_bronze(client, db_session):
    # One winner, two tied second -> ranks 1,2,2,4. The 4th row has placed third and
    # must get bronze; `rank <= 3` would deny it.
    meet = make_meet(db_session)
    for value in ("9.00", "8.00", "8.00", "7.00"):
        entry = make_meet_entry(
            db_session, meet=meet, gymnast=make_gymnast(db_session), level=Level.level_5
        )
        routine = make_routine(db_session, meet_entry=entry, apparatus=Apparatus.hoop)
        make_judge_score(
            db_session,
            routine=routine,
            judge=make_judge(db_session, first_name=f"J{value}{entry.id}"),
            panel=Panel.execution,
            value=Decimal(value),
        )
    db_session.commit()

    response = client.get(
        f"/meets/{meet.id}/standings",
        params={"apparatus": "hoop", "level": "level_5"},
    )

    rows = response.json()["rankings"]
    assert [row["rank"] for row in rows] == [1, 2, 2, 4]
    assert [row["medal"] for row in rows] == ["gold", "silver", "silver", "bronze"]
```

Note: `make_judge` is called with distinct `first_name` values because `uq_judge_identity` is `(first_name, last_name, country_code)`.

- [ ] **Step 7: Run the full backend suite**

Run from the repo root: `make test`
Expected: PASS. Existing results-router tests that assert cutoff medals on level 8+ rows encode the superseded rule — update them to expect placement medals.

- [ ] **Step 8: Lint and commit**

```bash
cd backend && ruff check . && ruff format .
git add backend/app/scoring.py backend/app/routers/results.py backend/test/test_scoring.py backend/test/test_routers/test_results_router.py
git commit -m "feat: award placement medals at levels 4+ and keep cutoffs for 1-3"
```

---

### Task 5: Frontend score-math mirror

`score-math.ts` mirrors `scoring.py`. This task ports the band table, adds the E deduction conversion helpers, and reshapes `computePreview` to group marks by panel exactly as the backend does.

**Files:**
- Modify: `frontend/src/lib/score-math.ts` (whole file)
- Test: `frontend/test/lib/score-math.test.ts`

**Interfaces:**
- Consumes: nothing from earlier tasks at runtime; mirrors Task 2/3's table and math.
- Produces:
  - `type Band = "1-3" | "4-7" | "8+"`
  - `type MedalMode = "cutoff" | "placement"`
  - `interface ScoringProfile { band: Band; panels: readonly string[]; medalMode: MedalMode; tieBreakOnExecution: boolean }`
  - `profileForLevel(level: string): ScoringProfile`
  - `E_MAX = 10`, `deductionToScore(deduction: number): number`, `scoreToDeduction(score: number): number`
  - `interface PreviewInput { band: Band; dBodyScores?: number[]; dAppScores?: number[]; artistryScores?: number[]; eScores?: number[]; finalScore?: number; penalty?: number }`
  - `interface ScorePreview { d: number; a: number; e: number; final: number; penalty: number; total: number }`
  - `computePreview(input: PreviewInput): ScorePreview`
  - `isEOnlyLevel(level: string): boolean` — kept as a **deprecated shim** over the new
    table so `ScoreForm`/`ScoringPage` keep compiling until Tasks 7–8 stop calling it.
    Task 8 deletes it. Every commit in Tasks 5–8 must pass `npm run build`.

- [ ] **Step 1: Write the failing tests**

Replace the contents of `frontend/test/lib/score-math.test.ts` with:

```ts
import { describe, expect, it } from "vitest";
import {
  computePreview,
  deductionToScore,
  profileForLevel,
  scoreToDeduction,
  trimmedMean,
} from "../../src/lib/score-math";

describe("trimmedMean", () => {
  it("plain-averages below the trim threshold", () => {
    expect(trimmedMean([8.8, 9.5, 7.2])).toBeCloseTo(8.5, 10);
    expect(trimmedMean([7.9, 8.3])).toBeCloseTo(8.1, 10);
    expect(trimmedMean([])).toBe(0);
  });

  it("drops the highest and lowest at or above the threshold", () => {
    expect(trimmedMean([8.5, 8.6, 8.7, 9.9])).toBeCloseTo(8.65, 10);
  });
});

describe("profileForLevel", () => {
  it("bands levels 1-3 as pre-aggregated with cutoff medals", () => {
    const profile = profileForLevel("level_2");
    expect(profile.band).toBe("1-3");
    expect(profile.panels).toEqual(["final"]);
    expect(profile.medalMode).toBe("cutoff");
    expect(profile.tieBreakOnExecution).toBe(false);
  });

  it("bands levels 4-7 as DB + E with placement medals", () => {
    const profile = profileForLevel("level_6");
    expect(profile.band).toBe("4-7");
    expect(profile.panels).toEqual(["difficulty_body", "execution"]);
    expect(profile.medalMode).toBe("placement");
    expect(profile.tieBreakOnExecution).toBe(false);
  });

  it("bands level 8 and above as the full FIG panel", () => {
    for (const level of ["level_8", "high_performance_1", "senior", "olympic"]) {
      expect(profileForLevel(level).band).toBe("8+");
    }
    expect(profileForLevel("senior").tieBreakOnExecution).toBe(true);
  });

  it("falls back to 8+ for an unrecognised level rather than throwing", () => {
    // The level string comes off the wire; the UI must not crash on a level the
    // frontend has not been rebuilt for. The backend deliberately does the opposite
    // and raises, because there the enum is exhaustive.
    expect(profileForLevel("level_99").band).toBe("8+");
  });
});

describe("E deduction round trip", () => {
  it("converts a deduction to a stored execution score", () => {
    expect(deductionToScore(1.5)).toBe(8.5);
    expect(deductionToScore(0)).toBe(10);
    expect(deductionToScore(10)).toBe(0);
  });

  it("converts a stored execution score back to a deduction", () => {
    expect(scoreToDeduction(8.5)).toBe(1.5);
    expect(scoreToDeduction(10)).toBe(0);
  });

  it("round-trips on 0.05 increments without drift", () => {
    for (let step = 0; step <= 200; step += 1) {
      const deduction = step * 0.05;
      expect(scoreToDeduction(deductionToScore(deduction))).toBeCloseTo(deduction, 10);
    }
  });
});

describe("computePreview", () => {
  it("records the final mark at levels 1-3", () => {
    expect(computePreview({ band: "1-3", finalScore: 11.75 })).toEqual({
      d: 0,
      a: 0,
      e: 0,
      final: 11.75,
      penalty: 0,
      total: 11.75,
    });
  });

  it("subtracts penalty from the final mark at levels 1-3", () => {
    expect(computePreview({ band: "1-3", finalScore: 12, penalty: 0.3 }).total).toBeCloseTo(
      11.7,
      10,
    );
  });

  it("averages the two DB marks at levels 4-7", () => {
    const preview = computePreview({
      band: "4-7",
      dBodyScores: [2.4, 2.6],
      eScores: [8.5, 8.7],
    });
    expect(preview.d).toBeCloseTo(2.5, 10);
    expect(preview.e).toBeCloseTo(8.6, 10);
    expect(preview.final).toBe(0);
    expect(preview.total).toBeCloseTo(11.1, 10);
  });

  it("sums DB and DA and trims E at 8+", () => {
    const preview = computePreview({
      band: "8+",
      dBodyScores: [5],
      dAppScores: [3],
      artistryScores: [8, 8.5],
      eScores: [8.5, 8.6, 8.7, 9.9],
    });
    expect(preview.d).toBeCloseTo(8, 10);
    expect(preview.a).toBeCloseTo(8.25, 10);
    expect(preview.e).toBeCloseTo(8.65, 10);
    expect(preview.total).toBeCloseTo(24.9, 10);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- --run test/lib/score-math.test.ts`
Expected: FAIL — `profileForLevel is not a function` / no such export.

- [ ] **Step 3: Rewrite score-math.ts**

Replace the contents of `frontend/src/lib/score-math.ts` with:

```ts
/**
 * Mirrors backend/app/scoring.py — keep the worked examples in the tests in sync.
 *
 * The band table below is the frontend half of the spec's "one declarative scoring
 * profile" decision (docs/superpowers/specs/2026-07-20-level-banded-scoring-design.md).
 * Any change here needs the matching change in app/scoring.py, and vice versa.
 */

export const TRIM_THRESHOLD = 4;

/** Execution is a score out of 10 at EVERY level; the form is what speaks deductions. */
export const E_MAX = 10;

export type Band = "1-3" | "4-7" | "8+";
export type MedalMode = "cutoff" | "placement";

export interface ScoringProfile {
  band: Band;
  /** Panel values (matching the API's Panel enum) that are legal at this band. */
  panels: readonly string[];
  medalMode: MedalMode;
  tieBreakOnExecution: boolean;
}

const BAND_1_3: ScoringProfile = {
  band: "1-3",
  panels: ["final"],
  medalMode: "cutoff",
  tieBreakOnExecution: false,
};

const BAND_4_7: ScoringProfile = {
  band: "4-7",
  panels: ["difficulty_body", "execution"],
  medalMode: "placement",
  tieBreakOnExecution: false,
};

const BAND_8_PLUS: ScoringProfile = {
  band: "8+",
  panels: ["difficulty_body", "difficulty_apparatus", "artistry", "execution"],
  medalMode: "placement",
  tieBreakOnExecution: true,
};

const PROFILE_BY_LEVEL: Readonly<Record<string, ScoringProfile>> = {
  level_1: BAND_1_3,
  level_2: BAND_1_3,
  level_3: BAND_1_3,
  level_4: BAND_4_7,
  level_5: BAND_4_7,
  level_6: BAND_4_7,
  level_7: BAND_4_7,
};

/**
 * The scoring band governing `level`.
 *
 * Deliberately falls back to 8+ for an unknown level instead of throwing — unlike the
 * backend, which builds its map exhaustively over the Level enum and raises. The level
 * string arrives off the wire here, and a UI that crashes mid-meet on a level added
 * server-side is worse than one that shows the full panel.
 */
export function profileForLevel(level: string): ScoringProfile {
  return PROFILE_BY_LEVEL[level] ?? BAND_8_PLUS;
}

/**
 * @deprecated Superseded by profileForLevel. A temporary shim so ScoreForm and
 * ScoringPage keep compiling while they are migrated to the band table; deleted once
 * they no longer call it. Preserves the old semantics exactly: levels 1-7 were the
 * "Execution only" set, which is every band below 8+.
 */
export function isEOnlyLevel(level: string): boolean {
  return profileForLevel(level).band !== "8+";
}

/** Guards against binary-float dust (10 - 0.05) reaching the 0.05-increment check. */
function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

/**
 * Save direction of the E round trip: a judge writes 1.5 meaning "1.5 off", and the
 * API stores the resulting execution score 8.5. See scoreToDeduction for the inverse —
 * both directions are required, or a judge reopening a routine sees 8.50 in the box
 * where they typed 1.50.
 *
 * Levels 1-3 are NOT deductions: that band's single mark is a straight score out of 13
 * and is neither converted nor inverted.
 */
export function deductionToScore(deduction: number): number {
  return round2(E_MAX - deduction);
}

/** Load direction of the E round trip. See deductionToScore. */
export function scoreToDeduction(score: number): number {
  return round2(E_MAX - score);
}

/** Below TRIM_THRESHOLD scores: plain average. At/above: drop high+low, average rest. */
export function trimmedMean(scores: number[]): number {
  if (scores.length === 0) return 0;
  if (scores.length < TRIM_THRESHOLD) {
    return scores.reduce((a, b) => a + b, 0) / scores.length;
  }
  const trimmed = [...scores].sort((a, b) => a - b).slice(1, -1);
  return trimmed.reduce((a, b) => a + b, 0) / trimmed.length;
}

/**
 * Marks grouped by panel, exactly as compute_routine_score groups them — so that the
 * two-DB-judges case at levels 4-7 and the four-E-judges case at 8+ reduce through the
 * same code path on both sides. `eScores` are execution SCORES here, already converted
 * from the form's deductions.
 */
export interface PreviewInput {
  band: Band;
  dBodyScores?: number[];
  dAppScores?: number[];
  artistryScores?: number[];
  eScores?: number[];
  finalScore?: number;
  penalty?: number;
}

export interface ScorePreview {
  d: number;
  a: number;
  e: number;
  final: number;
  penalty: number;
  total: number;
}

/**
 * Client-side preview only — server standings are the source of truth. The server
 * computes with Decimal; this uses binary floats, so the displayed total can drift
 * from the server's by ±0.01 in rare rounding cases. Never persist these numbers.
 */
export function computePreview(input: PreviewInput): ScorePreview {
  const penalty = input.penalty ?? 0;

  if (input.band === "1-3") {
    // Pre-aggregated: the entered mark IS the routine's score, less penalty.
    const final = input.finalScore ?? 0;
    return { d: 0, a: 0, e: 0, final, penalty, total: final - penalty };
  }

  // At 4-7 there is no DA, so trimmedMean([]) is 0 and (DB + DA) reduces to the
  // required average of the two DB marks — adding zero is a no-op, same as the backend.
  const d = trimmedMean(input.dBodyScores ?? []) + trimmedMean(input.dAppScores ?? []);
  const a = trimmedMean(input.artistryScores ?? []);
  const e = trimmedMean(input.eScores ?? []);
  return { d, a, e, final: 0, penalty, total: d + a + e - penalty };
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- --run test/lib/score-math.test.ts`
Expected: PASS.

- [ ] **Step 5: Verify the whole frontend still builds**

Run: `cd frontend && npm test -- --run && npm run build`
Expected: PASS on both. `ScoreForm.tsx` and `ScoringPage.tsx` still call `isEOnlyLevel`, which is why the shim exists — this task must not leave the typecheck broken.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/score-math.ts frontend/test/lib/score-math.test.ts
git commit -m "feat: mirror the three-band scoring profile in score-math"
```

---

### Task 6: Judge panel slots per band

The panel UI has slots `D, A, E1–E4`. It needs a single final slot at 1–3, DB1/DB2 at 4–7, and A1/A2 at 8+ (spec, "Consequences to handle" #3).

**Files:**
- Modify: `frontend/src/features/scoring/panel-storage.ts`
- Modify: `frontend/src/features/scoring/PanelSetupDialog.tsx`
- Test: `frontend/test/features/scoring/panel-storage.test.ts`, `frontend/test/features/scoring/PanelSetupDialog.test.tsx`

**Interfaces:**
- Consumes: `Band`, `profileForLevel` (Task 5).
- Produces:
  - `type PanelSlot = "F" | "D" | "DB1" | "DB2" | "A1" | "A2" | "E1" | "E2" | "E3" | "E4"`
  - `PANEL_SLOTS: PanelSlot[]` (in that order)
  - `SLOTS_BY_BAND: Record<Band, PanelSlot[]>`
  - `REQUIRED_SLOTS: Record<Band, PanelSlot[]>`
  - `loadPanel(meetId: number): PanelAssignment` — now migrates a legacy `A` key to `A1`
  - `savePanel(meetId: number, panel: PanelAssignment): void` (unchanged)

- [ ] **Step 1: Write the failing tests**

Append to `frontend/test/features/scoring/panel-storage.test.ts`:

```ts
it("migrates a legacy A slot to A1", () => {
  // Panels saved before the 8+ band gained a second artistry judge used a single "A".
  localStorage.setItem("rhythmiq.panel.7", JSON.stringify({ D: 1, A: 2, E1: 3 }));

  expect(loadPanel(7)).toEqual({ D: 1, A1: 2, E1: 3 });
});

it("does not let a legacy A overwrite an explicit A1", () => {
  localStorage.setItem("rhythmiq.panel.7", JSON.stringify({ A: 2, A1: 9 }));

  expect(loadPanel(7)).toEqual({ A1: 9 });
});

it("keeps the new slots", () => {
  localStorage.setItem(
    "rhythmiq.panel.7",
    JSON.stringify({ F: 1, DB1: 2, DB2: 3, A1: 4, A2: 5 }),
  );

  expect(loadPanel(7)).toEqual({ F: 1, DB1: 2, DB2: 3, A1: 4, A2: 5 });
});

it("maps each band to the slots that band actually uses", () => {
  expect(SLOTS_BY_BAND["1-3"]).toEqual(["F"]);
  expect(SLOTS_BY_BAND["4-7"]).toEqual(["DB1", "DB2", "E1", "E2"]);
  expect(SLOTS_BY_BAND["8+"]).toEqual(["D", "A1", "A2", "E1", "E2", "E3", "E4"]);
});

it("requires the minimum viable panel per band", () => {
  // E3/E4 and A2 legitimately stay empty on a small panel, as before.
  expect(REQUIRED_SLOTS["1-3"]).toEqual(["F"]);
  expect(REQUIRED_SLOTS["4-7"]).toEqual(["DB1", "DB2", "E1", "E2"]);
  expect(REQUIRED_SLOTS["8+"]).toEqual(["D", "A1", "E1", "E2"]);
});
```

Update that file's import to `import { loadPanel, savePanel, PANEL_SLOTS, SLOTS_BY_BAND, REQUIRED_SLOTS } from "../../../src/features/scoring/panel-storage";` (keep whatever it already imports).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- --run test/features/scoring/panel-storage.test.ts`
Expected: FAIL — `SLOTS_BY_BAND` is not exported; the legacy-migration test returns `{ D: 1, E1: 3 }`.

- [ ] **Step 3: Rewrite panel-storage.ts**

Replace the contents of `frontend/src/features/scoring/panel-storage.ts` with:

```ts
import type { Band } from "../../lib/score-math";

/**
 * Judge slots across all three scoring bands. "D" is the 8+ difficulty judge and covers
 * both D-Body and D-App (one judge, two marks, two panels — legal because JudgeScore is
 * unique on (routine, judge, panel)). Levels 4-7 instead have TWO body judges, DB1/DB2,
 * and no apparatus difficulty at all — the asymmetry is deliberate, see the spec.
 */
export type PanelSlot =
  | "F"
  | "D"
  | "DB1"
  | "DB2"
  | "A1"
  | "A2"
  | "E1"
  | "E2"
  | "E3"
  | "E4";

export const PANEL_SLOTS: PanelSlot[] = [
  "F",
  "D",
  "DB1",
  "DB2",
  "A1",
  "A2",
  "E1",
  "E2",
  "E3",
  "E4",
];

/** Which slots each band actually uses — drives the setup dialog's grouping. */
export const SLOTS_BY_BAND: Record<Band, PanelSlot[]> = {
  "1-3": ["F"],
  "4-7": ["DB1", "DB2", "E1", "E2"],
  "8+": ["D", "A1", "A2", "E1", "E2", "E3", "E4"],
};

/** The minimum viable panel per band; E3/E4 and A2 legitimately stay empty. */
export const REQUIRED_SLOTS: Record<Band, PanelSlot[]> = {
  "1-3": ["F"],
  "4-7": ["DB1", "DB2", "E1", "E2"],
  "8+": ["D", "A1", "E1", "E2"],
};

/**
 * Slots that write to the same API panel, and therefore may not share a judge — a
 * second mark from the same judge on the same panel violates
 * uq_judge_score_routine_judge_panel and the save would fail at the API.
 */
export const SLOT_CONFLICT_GROUPS: PanelSlot[][] = [
  ["DB1", "DB2"],
  ["A1", "A2"],
  ["E1", "E2", "E3", "E4"],
];

/** Slot -> judge id. Missing slot = no judge assigned (its boxes render disabled). */
export type PanelAssignment = Partial<Record<PanelSlot, number>>;

const key = (meetId: number) => `rhythmiq.panel.${meetId}`;

export function loadPanel(meetId: number): PanelAssignment {
  try {
    const raw = localStorage.getItem(key(meetId));
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return {};
    // Keep only known slots with numeric judge ids: a junk value like "x" would read
    // as an assigned judge downstream (boxesFor only checks !== undefined).
    const stored = parsed as Record<string, unknown>;
    const panel: PanelAssignment = {};
    for (const slot of PANEL_SLOTS) {
      const judgeId = stored[slot];
      if (typeof judgeId === "number") panel[slot] = judgeId;
    }
    // Panels saved before 8+ gained a second artistry judge used a single "A" slot.
    // Read it as A1 rather than dropping it, so a meet in progress keeps its panel.
    // An explicit A1 wins — it is the newer of the two.
    if (panel.A1 === undefined && typeof stored.A === "number") {
      panel.A1 = stored.A;
    }
    return panel;
  } catch {
    return {};
  }
}

export function savePanel(meetId: number, panel: PanelAssignment): void {
  localStorage.setItem(key(meetId), JSON.stringify(panel));
}
```

- [ ] **Step 4: Run the storage tests to verify they pass**

Run: `cd frontend && npm test -- --run test/features/scoring/panel-storage.test.ts`
Expected: PASS.

- [ ] **Step 5: Write the failing dialog test**

Append to `frontend/test/features/scoring/PanelSetupDialog.test.tsx`:

```tsx
it("groups the slots by scoring band", async () => {
  render(
    <PanelSetupDialog
      open
      value={{}}
      judges={[judge(1, "Ann"), judge(2, "Bo")]}
      onSave={vi.fn()}
      onClose={vi.fn()}
    />,
  );

  expect(screen.getByText(/Levels 1–3/)).toBeInTheDocument();
  expect(screen.getByText(/Levels 4–7/)).toBeInTheDocument();
  expect(screen.getByText(/Levels 8\+/)).toBeInTheDocument();
  expect(screen.getByLabelText("F")).toBeInTheDocument();
  expect(screen.getByLabelText("DB1")).toBeInTheDocument();
  expect(screen.getByLabelText("A2")).toBeInTheDocument();
});

it("rejects the same judge in two difficulty-body slots", async () => {
  const onSave = vi.fn();
  const user = userEvent.setup();
  render(
    <PanelSetupDialog
      open
      value={{}}
      judges={[judge(1, "Ann"), judge(2, "Bo")]}
      onSave={onSave}
      onClose={vi.fn()}
    />,
  );

  await user.selectOptions(screen.getByLabelText("DB1"), "1");
  await user.selectOptions(screen.getByLabelText("DB2"), "1");
  await user.click(screen.getByRole("button", { name: "Save panel" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The same judge can't sit in two Difficulty (Body) slots.",
  );
  expect(onSave).not.toHaveBeenCalled();
});

it("rejects the same judge in two artistry slots", async () => {
  const onSave = vi.fn();
  const user = userEvent.setup();
  render(
    <PanelSetupDialog
      open
      value={{}}
      judges={[judge(1, "Ann"), judge(2, "Bo")]}
      onSave={onSave}
      onClose={vi.fn()}
    />,
  );

  await user.selectOptions(screen.getByLabelText("A1"), "2");
  await user.selectOptions(screen.getByLabelText("A2"), "2");
  await user.click(screen.getByRole("button", { name: "Save panel" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The same judge can't sit in two Artistry slots.",
  );
  expect(onSave).not.toHaveBeenCalled();
});
```

Define the `judge` helper at the top of the file if it does not already exist:

```tsx
const judge = (id: number, first_name: string) =>
  ({ id, first_name, last_name: "Judge", country_code: null, category: null }) as JudgeRead;
```

- [ ] **Step 6: Run the dialog test to verify it fails**

Run: `cd frontend && npm test -- --run test/features/scoring/PanelSetupDialog.test.tsx`
Expected: FAIL — `Unable to find a label with the text of: F`.

- [ ] **Step 7: Rewrite the dialog**

Replace the contents of `frontend/src/features/scoring/PanelSetupDialog.tsx` with:

```tsx
import { useState } from "react";
import type { JudgeRead } from "../../api/types";
import type { Band } from "../../lib/score-math";
import {
  SLOTS_BY_BAND,
  SLOT_CONFLICT_GROUPS,
  type PanelAssignment,
  type PanelSlot,
} from "./panel-storage";

const BAND_HEADINGS: Record<Band, string> = {
  "1-3": "Levels 1–3 — one final mark out of 13",
  "4-7": "Levels 4–7 — two Difficulty (Body) judges, two Execution",
  "8+": "Levels 8+ — full FIG panel",
};

const BANDS: Band[] = ["1-3", "4-7", "8+"];

const CONFLICT_LABELS: Record<string, string> = {
  DB1: "Difficulty (Body)",
  A1: "Artistry",
  E1: "Execution",
};

export function PanelSetupDialog({
  open,
  value,
  judges,
  onSave,
  onClose,
}: {
  open: boolean;
  value: PanelAssignment;
  judges: JudgeRead[];
  onSave: (panel: PanelAssignment) => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState<PanelAssignment>(value);
  const [wasOpen, setWasOpen] = useState(open);
  const [error, setError] = useState<string | null>(null);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) {
      setDraft(value);
      setError(null);
    }
  }
  if (!open) return null;

  const setSlot = (slot: PanelSlot, judgeId: string) => {
    setError(null);
    setDraft((d) => {
      const next = { ...d };
      if (judgeId === "") delete next[slot];
      else next[slot] = Number(judgeId);
      return next;
    });
  };

  const handleSave = () => {
    // Slots in the same group write to the same API panel, and JudgeScore is unique on
    // (routine, judge, panel) — a duplicate here would fail at save time, mid-meet.
    for (const group of SLOT_CONFLICT_GROUPS) {
      const ids = group
        .map((slot) => draft[slot])
        .filter((id): id is number => id !== undefined);
      if (new Set(ids).size !== ids.length) {
        setError(
          `The same judge can't sit in two ${CONFLICT_LABELS[group[0]]} slots.`,
        );
        return;
      }
    }
    onSave(draft);
  };

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black/30">
      <div className="w-96 rounded border border-gray-200 bg-white p-4 shadow-lg">
        <h2 className="mb-2 text-lg font-semibold">Judge panel for this meet</h2>
        <p className="mb-3 text-xs text-gray-500">
          Set once when the meet starts; every save attributes scores to these judges.
          A meet can span several levels, so fill in the bands you are running. The 8+
          D judge covers both D-Body and D-App.
        </p>
        {BANDS.map((band) => (
          <div key={band} className="mb-3">
            <h3 className="mb-1 text-xs font-semibold uppercase text-gray-500">
              {BAND_HEADINGS[band]}
            </h3>
            <div className="grid grid-cols-[3rem_1fr] items-center gap-2">
              {SLOTS_BY_BAND[band].map((slot) => (
                <label key={slot} className="contents text-sm">
                  <span className="text-xs font-semibold uppercase">{slot}</span>
                  <select
                    aria-label={slot}
                    value={draft[slot] ?? ""}
                    onChange={(e) => setSlot(slot, e.target.value)}
                    className="rounded border border-gray-300 p-1"
                  >
                    <option value="">— unassigned —</option>
                    {judges.map((j) => (
                      <option key={j.id} value={j.id}>
                        {j.first_name} {j.last_name}
                        {j.country_code ? ` (${j.country_code})` : ""}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
          </div>
        ))}
        {error && (
          <p role="alert" className="mt-2 text-xs text-red-700">
            {error}
          </p>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded border border-gray-300 px-3 py-1 text-sm">
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white"
          >
            Save panel
          </button>
        </div>
      </div>
    </div>
  );
}
```

Note: `E1` and `E2` appear in both the 4–7 and 8+ groups, so their `aria-label` is not unique across the dialog. If `getByLabelText("E1")` in the existing tests now throws "found multiple elements", disambiguate by rendering the slot label as `` `${band} ${slot}` `` in the `aria-label` and updating the tests — but prefer keeping the plain slot label and using `getAllByLabelText` in tests, since the slot genuinely is one shared assignment.

- [ ] **Step 8: Run the dialog tests to verify they pass**

Run: `cd frontend && npm test -- --run test/features/scoring/PanelSetupDialog.test.tsx`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/features/scoring/panel-storage.ts frontend/src/features/scoring/PanelSetupDialog.tsx frontend/test/features/scoring/panel-storage.test.ts frontend/test/features/scoring/PanelSetupDialog.test.tsx
git commit -m "feat: add per-band judge panel slots and conflict checks"
```

---

### Task 7: `ScoreForm` — band-dependent boxes and the E round trip

**Files:**
- Modify: `frontend/src/features/scoring/save-diff.ts` (`BoxKey`)
- Modify: `frontend/src/features/scoring/ScoreForm.tsx`
- Test: `frontend/test/features/scoring/save-diff.test.ts`, `frontend/test/features/scoring/ScoringPage.test.tsx`

**Interfaces:**
- Consumes: `Band`, `profileForLevel`, `computePreview`, `deductionToScore`, `scoreToDeduction` (Task 5); `PanelAssignment` (Task 6).
- Produces:
  - `type BoxKey = "final" | "dBody1" | "dBody2" | "dApp" | "a1" | "a2" | "e1" | "e2" | "e3" | "e4"`
  - `boxesFor(panel: PanelAssignment, band: Band): BoxDef[]` — signature gains `band`; the returned list is exactly the boxes to render (no downstream filtering)
  - `E_BOX_KEYS: BoxKey[]` exported from `ScoreForm.tsx`

- [ ] **Step 1: Update `BoxKey`**

In `frontend/src/features/scoring/save-diff.ts`, replace the `BoxKey` type:

```ts
export type BoxKey =
  | "final"
  | "dBody1"
  | "dBody2"
  | "dApp"
  | "a1"
  | "a2"
  | "e1"
  | "e2"
  | "e3"
  | "e4";
```

`computeSaveOps` itself is unchanged — it is already keyed on `(judge, panel)` and does not know about bands. Update any `BoxKey` literals in `frontend/test/features/scoring/save-diff.test.ts` (`"a"` → `"a1"`, `"dBody"` → `"dBody1"`).

- [ ] **Step 2: Write the failing form tests**

Append to `frontend/test/features/scoring/ScoringPage.test.tsx` (follow the file's existing setup for rendering the scoring page with MSW-backed entries; the assertions are what matter):

```tsx
it("shows one final box at levels 1-3", async () => {
  await renderScoringPageWithEntry({ level: "level_1" });

  expect(await screen.findByLabelText("Final")).toBeInTheDocument();
  expect(screen.queryByLabelText("E1")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("D-Body 1")).not.toBeInTheDocument();
});

it("shows two D-Body boxes and two E boxes at levels 4-7", async () => {
  await renderScoringPageWithEntry({ level: "level_5" });

  expect(await screen.findByLabelText("D-Body 1")).toBeInTheDocument();
  expect(screen.getByLabelText("D-Body 2")).toBeInTheDocument();
  expect(screen.getByLabelText("E1")).toBeInTheDocument();
  expect(screen.getByLabelText("E2")).toBeInTheDocument();
  expect(screen.queryByLabelText("E3")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("D-App")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Artistry 1")).not.toBeInTheDocument();
});

it("shows the full panel at 8+", async () => {
  await renderScoringPageWithEntry({ level: "level_8" });

  expect(await screen.findByLabelText("D-Body 1")).toBeInTheDocument();
  expect(screen.getByLabelText("D-App")).toBeInTheDocument();
  expect(screen.getByLabelText("Artistry 1")).toBeInTheDocument();
  expect(screen.getByLabelText("Artistry 2")).toBeInTheDocument();
  expect(screen.getByLabelText("E4")).toBeInTheDocument();
});

it("saves an E deduction as an execution score", async () => {
  const user = userEvent.setup();
  const posted = captureJudgeScorePosts();
  await renderScoringPageWithEntry({ level: "level_8" });

  await user.type(await screen.findByLabelText("E1"), "1.50");
  await user.click(screen.getByRole("button", { name: "Save" }));

  await waitFor(() => expect(posted()).toHaveLength(1));
  expect(posted()[0]).toMatchObject({ panel: "execution", value: "8.50" });
});

it("shows a stored execution score back as a deduction", async () => {
  await renderScoringPageWithEntry({
    level: "level_8",
    existingScores: [{ id: 1, judge_id: 3, panel: "execution", value: "8.50" }],
  });

  expect(await screen.findByLabelText("E1")).toHaveValue("1.50");
});

it("saves a level 1-3 final mark as entered, without conversion", async () => {
  const user = userEvent.setup();
  const posted = captureJudgeScorePosts();
  await renderScoringPageWithEntry({ level: "level_1" });

  await user.type(await screen.findByLabelText("Final"), "11.50");
  await user.click(screen.getByRole("button", { name: "Save" }));

  await waitFor(() => expect(posted()).toHaveLength(1));
  expect(posted()[0]).toMatchObject({ panel: "final", value: "11.50" });
});

it("rejects a deduction above 10", async () => {
  const user = userEvent.setup();
  await renderScoringPageWithEntry({ level: "level_8" });

  await user.type(await screen.findByLabelText("E1"), "11");
  await user.click(screen.getByRole("button", { name: "Save" }));

  expect(await screen.findByText("Max 10")).toBeInTheDocument();
});

it("accepts a final mark up to 13", async () => {
  const user = userEvent.setup();
  await renderScoringPageWithEntry({ level: "level_1" });

  await user.type(await screen.findByLabelText("Final"), "13.05");
  await user.click(screen.getByRole("button", { name: "Save" }));

  expect(await screen.findByText("Max 13")).toBeInTheDocument();
});
```

Add the two helpers near the top of the test file if they do not already exist — `renderScoringPageWithEntry({ level, existingScores })` renders `ScoringPage` with an MSW handler returning one meet entry at that level plus a saved panel assignment in `localStorage` covering every slot, and `captureJudgeScorePosts()` installs an MSW `POST /api/judge-scores/` handler that records request bodies and returns 201. Model both on the file's existing render/MSW helpers rather than inventing a new pattern.

- [ ] **Step 3: Run the form tests to verify they fail**

Run: `cd frontend && npm test -- --run test/features/scoring/ScoringPage.test.tsx`
Expected: FAIL — `Unable to find a label with the text of: Final`.

- [ ] **Step 4: Rewrite the box layout, labels, validation and preview wiring**

In `frontend/src/features/scoring/ScoreForm.tsx`, replace lines 1–63 (imports through `validateBox`) with:

```tsx
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { toNum } from "../../api/client";
import type {
  Apparatus,
  JudgeScoreRead,
  MeetEntryRead,
  Panel,
  RoutineRead,
} from "../../api/types";
import {
  computePreview,
  deductionToScore,
  profileForLevel,
  scoreToDeduction,
  type Band,
} from "../../lib/score-math";
import type { PanelAssignment } from "./panel-storage";
import type { BoxDef, BoxKey } from "./save-diff";
import { saveScores, type SaveScoresResult } from "./save-scores";

const BOX_LABELS: Record<BoxKey, string> = {
  final: "Final",
  dBody1: "D-Body 1",
  dBody2: "D-Body 2",
  dApp: "D-App",
  a1: "Artistry 1",
  a2: "Artistry 2",
  e1: "E1",
  e2: "E2",
  e3: "E3",
  e4: "E4",
};

export const E_BOX_KEYS: BoxKey[] = ["e1", "e2", "e3", "e4"];

/** Per-box ceiling; undefined = uncapped, mirroring ck_judge_score_panel_value_cap. */
const BOX_MAX: Partial<Record<BoxKey | "penalty", number>> = {
  final: 13,
  a1: 10,
  a2: 10,
  e1: 10,
  e2: 10,
  e3: 10,
  e4: 10,
};

type FormValues = Record<BoxKey | "penalty", string>;

const EMPTY_VALUES: FormValues = {
  final: "",
  dBody1: "",
  dBody2: "",
  dApp: "",
  a1: "",
  a2: "",
  e1: "",
  e2: "",
  e3: "",
  e4: "",
  penalty: "",
};

/**
 * The boxes to render for `band`, already filtered — there is no separate "visible"
 * subset. Levels 4-7 have TWO D-Body judges and no D-App at all; levels 8+ have one
 * D judge covering both difficulty panels. See the spec's "Deliberate asymmetry".
 */
export function boxesFor(panel: PanelAssignment, band: Band): BoxDef[] {
  if (band === "1-3") {
    return [{ key: "final", panel: "final" as Panel, judgeId: panel.F }];
  }
  if (band === "4-7") {
    return [
      { key: "dBody1", panel: "difficulty_body" as Panel, judgeId: panel.DB1 },
      { key: "dBody2", panel: "difficulty_body" as Panel, judgeId: panel.DB2 },
      { key: "e1", panel: "execution" as Panel, judgeId: panel.E1 },
      { key: "e2", panel: "execution" as Panel, judgeId: panel.E2 },
    ];
  }
  return [
    { key: "dBody1", panel: "difficulty_body" as Panel, judgeId: panel.D },
    { key: "dApp", panel: "difficulty_apparatus" as Panel, judgeId: panel.D },
    { key: "a1", panel: "artistry" as Panel, judgeId: panel.A1 },
    { key: "a2", panel: "artistry" as Panel, judgeId: panel.A2 },
    { key: "e1", panel: "execution" as Panel, judgeId: panel.E1 },
    { key: "e2", panel: "execution" as Panel, judgeId: panel.E2 },
    { key: "e3", panel: "execution" as Panel, judgeId: panel.E3 },
    { key: "e4", panel: "execution" as Panel, judgeId: panel.E4 },
  ];
}

// Unparseable text reads as "empty" so the live preview never shows NaN. Saves can't
// misread garbage as a cleared box (=> DELETE): submit is gated by validateBox, which
// rejects non-numbers before values reach the save diff.
function parseBox(s: string): number | undefined {
  const t = s.trim();
  if (t === "") return undefined;
  const n = Number(t);
  return Number.isNaN(n) ? undefined : n;
}

/**
 * "" ok; else numeric, >= 0, 0.05 steps, within the box's ceiling.
 *
 * E boxes hold DEDUCTIONS, which share Execution's 0-10 range: the stored score is
 * 10 - deduction, so a deduction outside 0-10 produces a value the DB rejects. Bound it
 * here rather than only at the API.
 */
function validateBox(key: BoxKey | "penalty", s: string): string | null {
  const t = s.trim();
  if (t === "") return null;
  const n = Number(t);
  if (Number.isNaN(n)) return "Not a number";
  if (n < 0) return "Must be ≥ 0";
  if (Math.round(n * 100) % 5 !== 0) return "Use 0.05 steps";
  const max = BOX_MAX[key];
  if (key !== "penalty" && max !== undefined && n > max) return `Max ${max}`;
  return null;
}
```

Then, inside the component, replace the band/box derivation (lines 86–90) with:

```tsx
  const band = profileForLevel(entry.level).band;
  const boxes = boxesFor(panel, band);
```

and replace every later use of `visibleBoxes` with `boxes` (the list is already band-filtered).

Replace the `defaultValues` memo body's loop so E boxes load as deductions:

```tsx
  const defaultValues = useMemo<FormValues>(() => {
    const values: FormValues = {
      ...EMPTY_VALUES,
      penalty:
        routine && toNum(routine.penalty) !== 0
          ? toNum(routine.penalty).toFixed(2)
          : "",
    };
    for (const box of boxes) {
      if (box.judgeId === undefined) continue;
      const existing = existingScores.find(
        (s) => s.judge_id === box.judgeId && s.panel === box.panel,
      );
      if (!existing) continue;
      const stored = toNum(existing.value);
      // Load direction of the E round trip: the API stores an execution score, the
      // judge typed a deduction. Without this inversion they would reopen a routine and
      // see 8.50 in the box where they entered 1.50.
      values[box.key] = E_BOX_KEYS.includes(box.key)
        ? scoreToDeduction(stored).toFixed(2)
        : stored.toFixed(2);
    }
    return values;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
```

Replace the preview call (lines 143–152):

```tsx
  const watched = watch();
  const preview = computePreview({
    band,
    // Marks are grouped by panel here exactly as the backend groups them, so the
    // two-DB-judge and four-E-judge cases reduce through the same code on both sides.
    dBodyScores: [parseBox(watched.dBody1), parseBox(watched.dBody2)].filter(
      (v): v is number => v !== undefined,
    ),
    dAppScores: [parseBox(watched.dApp)].filter((v): v is number => v !== undefined),
    artistryScores: [parseBox(watched.a1), parseBox(watched.a2)].filter(
      (v): v is number => v !== undefined,
    ),
    // The summary line shows the E SCORE, not the deduction total — it is what feeds
    // the total, and the total is what the scorer is checking.
    eScores: E_BOX_KEYS.map((k) => parseBox(watched[k]))
      .filter((v): v is number => v !== undefined)
      .map(deductionToScore),
    finalScore: parseBox(watched.final),
    penalty: parseBox(watched.penalty),
  });
```

Replace the `values:` argument inside `submit`'s `saveScores` call so E boxes convert on save:

```tsx
          values: Object.fromEntries(
            boxes.map((b) => {
              const raw = parseBox(values[b.key]);
              // Save direction of the E round trip: the judge types a deduction, the
              // API only ever receives an execution score.
              const value =
                raw !== undefined && E_BOX_KEYS.includes(b.key)
                  ? deductionToScore(raw)
                  : raw;
              return [b.key, value];
            }),
          ),
```

Replace the summary line (lines 244–253):

```tsx
      <div className="mt-4 flex gap-6 rounded border border-dashed border-gray-300 p-2 text-sm">
        {band === "1-3" && <span>Final: <strong>{fmt(preview.final)}</strong></span>}
        {band !== "1-3" && <span>D: <strong>{fmt(preview.d)}</strong></span>}
        {band === "8+" && <span>A: <strong>{fmt(preview.a)}</strong></span>}
        {band !== "1-3" && <span>E: <strong>{fmt(preview.e)}</strong></span>}
        {/* Only sign a penalty that exists -- "−0.00" reads as a negative zero. */}
        <span>
          Penalty: <strong>{preview.penalty === 0 ? fmt(0) : `−${fmt(preview.penalty)}`}</strong>
        </span>
        <span className="ml-auto">Total: <strong>{fmt(preview.total)}</strong></span>
      </div>
```

Finally, give each input an accessible name so the tests above can find it — in `boxInput`, add `aria-label` to the `<input>`:

```tsx
        aria-label={key === "penalty" ? "Penalty" : BOX_LABELS[key]}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && npm test -- --run test/features/scoring && npm run build`
Expected: PASS on both. `ScoringPage.tsx` still calls the deprecated `isEOnlyLevel` shim for its required-slot check — that is Task 8's job, and it must keep compiling until then.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/scoring/ScoreForm.tsx frontend/src/features/scoring/save-diff.ts frontend/test/features/scoring/
git commit -m "feat: make ScoreForm band-dependent and convert E deductions at the boundary"
```

---

### Task 8: `ScoringPage` required slots per band

This is also the task that retires the deprecated `isEOnlyLevel` shim, since `ScoringPage` is its last caller.

**Files:**
- Modify: `frontend/src/features/scoring/ScoringPage.tsx:8`, `:22-27`
- Modify: `frontend/src/lib/score-math.ts` (delete the `isEOnlyLevel` shim)
- Test: `frontend/test/features/scoring/ScoringPage.test.tsx`

**Interfaces:**
- Consumes: `profileForLevel` (Task 5), `REQUIRED_SLOTS` (Task 6).
- Produces: `isEOnlyLevel` no longer exists.

- [ ] **Step 1: Write the failing test**

Append to `frontend/test/features/scoring/ScoringPage.test.tsx`:

```tsx
it("warns about the band's own missing slots, not the 8+ ones", async () => {
  // A panel with only F filled is complete for a level-1 competitor.
  localStorage.setItem("rhythmiq.panel.1", JSON.stringify({ F: 3 }));
  await renderScoringPageWithEntry({ level: "level_1" });

  expect(await screen.findByLabelText("Final")).toBeInTheDocument();
  expect(screen.queryByText(/No judge assigned for/)).not.toBeInTheDocument();
});

it("names the 4-7 slots when they are missing", async () => {
  localStorage.setItem("rhythmiq.panel.1", JSON.stringify({ DB1: 3, E1: 4 }));
  await renderScoringPageWithEntry({ level: "level_5" });

  expect(await screen.findByText(/DB2, E2/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- --run test/features/scoring/ScoringPage.test.tsx`
Expected: FAIL — the page still asks for `E1, E2` at level 1 (or fails to compile on the missing `isEOnlyLevel` import).

- [ ] **Step 3: Derive the required slots from the band**

In `frontend/src/features/scoring/ScoringPage.tsx`, replace the `isEOnlyLevel` import (line 8) with:

```tsx
import { profileForLevel } from "../../lib/score-math";
```

add `REQUIRED_SLOTS` to the `panel-storage` import:

```tsx
import {
  loadPanel,
  savePanel,
  REQUIRED_SLOTS,
  type PanelAssignment,
  type PanelSlot,
} from "./panel-storage";
```

and replace `missingRequiredSlots` (lines 21–27):

```tsx
/**
 * The minimum viable panel for this competitor's band (see REQUIRED_SLOTS): E3/E4 and
 * the second artistry judge legitimately stay empty on a small panel.
 */
function missingRequiredSlots(panel: PanelAssignment, level: string): PanelSlot[] {
  const required = REQUIRED_SLOTS[profileForLevel(level).band];
  return required.filter((slot) => panel[slot] === undefined);
}
```

- [ ] **Step 4: Delete the deprecated shim**

`ScoringPage` was its last caller. Remove this block from `frontend/src/lib/score-math.ts`:

```ts
/**
 * @deprecated Superseded by profileForLevel. A temporary shim so ScoreForm and
 * ScoringPage keep compiling while they are migrated to the band table; deleted once
 * they no longer call it. Preserves the old semantics exactly: levels 1-7 were the
 * "Execution only" set, which is every band below 8+.
 */
export function isEOnlyLevel(level: string): boolean {
  return profileForLevel(level).band !== "8+";
}
```

Run `cd frontend && grep -rn "isEOnlyLevel" src test` first and confirm it returns nothing outside that block. If any caller remains, migrate it to `profileForLevel` rather than keeping the shim.

- [ ] **Step 5: Run the full frontend suite and typecheck**

Run: `cd frontend && npm test -- --run && npm run build`
Expected: PASS on both. `npm run build` is the typecheck gate — with the shim gone it must report no reference to `isEOnlyLevel`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/scoring/ScoringPage.tsx frontend/src/lib/score-math.ts frontend/test/features/scoring/ScoringPage.test.tsx
git commit -m "feat: require only the current band's judge slots on the scoring page"
```

---

### Task 9: Seed data, medal-cutoff copy, and documentation

Closes the spec's "Consequences to handle" #1 and #2, and brings CLAUDE.md in line with what now ships.

**Files:**
- Modify: `backend/scripts/seed_demo_data.py`
- Modify: `frontend/src/features/meets/MeetForm.tsx:148-170`
- Modify: `CLAUDE.md`
- Modify: `docs/superpowers/specs/2026-07-20-level-banded-scoring-design.md` (status line)

**Interfaces:**
- Consumes: everything above.
- Produces: nothing consumed downstream.

- [ ] **Step 1: Make the seed data band-correct**

In `backend/scripts/seed_demo_data.py`, find where judge scores are created and make each routine's marks match its entry's band: `Panel.final` only for levels 1–3, `difficulty_body` + `execution` (two judges each) for 4–7, and the full D/A/E set for 8+. A level-1 routine carrying an `execution` mark is now invalid data and would be silently ignored by `compute_routine_score`.

Add a comment above the medal cutoffs (around line 294):

```python
            # Medal cutoffs only apply to levels 1-3, and they are compared against the
            # ALL-AROUND total (2 apparatus at that band, so max 26) -- not a single
            # routine. 24.00 gold is a normal cutoff on that scale. Levels 4+ award
            # medals by placement and ignore these fields entirely.
            medal_gold_min=Decimal("24.00"),
            medal_silver_min=Decimal("21.00"),
```

- [ ] **Step 2: Verify the seed produces valid data**

Run from the repo root: `make reset && make dev && make seed`
Expected: completes without error.

Then check a level 1–3 all-around returns cutoff medals and a level 8+ standings returns placement medals:

```bash
curl -s "http://127.0.0.1:8000/meets/1/all-around?level=level_1" | head -c 400
curl -s "http://127.0.0.1:8000/meets/1/standings?apparatus=hoop&level=level_8" | head -c 400
```
Expected: the first shows `"medal"` values driven by the 24.00/21.00 cutoffs; the second shows `gold`/`silver`/`bronze` on the top three distinct ranks and `null` below.

- [ ] **Step 3: Fix the medal-cutoff copy (punch-list item A7)**

In `frontend/src/features/meets/MeetForm.tsx`, replace the two medal `<label>` blocks (lines 148–170) with:

```tsx
      <fieldset className="text-sm">
        <legend className="font-semibold">Medal cutoffs (levels 1–3 only)</legend>
        <p className="mb-2 text-xs text-gray-500">
          Minimum <strong>all-around</strong> totals, not per-routine scores. Levels 1–3
          compete on 2 apparatus at up to 13 each, so the scale is 0–26 — a gold
          cutoff around 24 is typical. Levels 4 and above award medals by placement and
          ignore these fields.
        </p>
        <label className="text-sm">
          Gold minimum
          <input
            type="number"
            step="0.01"
            {...register("medal_gold_min")}
            aria-label="Gold minimum"
            className={fieldClass}
          />
          {errors.medal_gold_min && (
            <span className="text-xs text-red-700">{errors.medal_gold_min.message}</span>
          )}
        </label>
        <label className="text-sm">
          Silver minimum
          <input
            type="number"
            step="0.01"
            {...register("medal_silver_min")}
            aria-label="Silver minimum"
            className={fieldClass}
          />
        </label>
      </fieldset>
```

- [ ] **Step 4: Run the frontend suite**

Run: `cd frontend && npm test -- --run && npm run build`
Expected: PASS. If a `MeetForm` test asserts on the old label structure, update it — the `aria-label`s are unchanged, so queries by accessible name still work.

- [ ] **Step 5: Update CLAUDE.md**

In the "Domain model specifics" section, replace the bullet describing results/reporting's tie-breaks and medals, and add a scoring-bands bullet:

```markdown
- **Scoring bands** (`app/scoring.py`, mirrored in `frontend/src/lib/score-math.ts`):
  one declarative band→profile table drives panel validity, D combination, tie-breaking
  and medal mode. Levels 1–3 record a single pre-aggregated mark on `Panel.final`
  (max 13, no averaging, no tie-break); levels 4–7 use two `difficulty_body` judges plus
  two `execution` judges, `avg(DB) + E`, max 13; levels 8+ use the full FIG panel with
  the Execution tie-break. The additive `DB + DA` formula covers 4–7 unchanged, since
  `trimmed_mean([])` is 0. Adding a level to the `Level` enum without assigning it a
  band fails `test_every_level_has_a_scoring_profile` — the backend map is exhaustive by
  construction; the frontend deliberately falls back to 8+ instead of throwing.
- **Two medal systems.** Levels 1–3 use `Meet.medal_gold_min`/`medal_silver_min` score
  cutoffs against the **all-around** (2 apparatus, max 26). Levels 4+ use placement:
  the first three **distinct ranks**, ties sharing a medal (`assign_placement_medals`) —
  never `rank <= 3`, which denies bronze when two competitors tie for silver. Ranks
  themselves stay competition-ranked (1,2,2,4); medal assignment is a separate pass.
- **Execution is always a score out of 10 in the database**, at every level, so the
  highest-E tie-break orders correctly. The score form speaks **deductions** and converts
  at its own boundary in both directions (`deductionToScore` / `scoreToDeduction` in
  `score-math.ts`). Levels 1–3 are not deductions and are stored exactly as entered.
```

Also update the frontend paragraph's mention of the panel localStorage key to note the slots are now `F, D, DB1, DB2, A1, A2, E1–E4`, with a legacy `A` key read as `A1`.

- [ ] **Step 6: Mark the spec implemented**

In `docs/superpowers/specs/2026-07-20-level-banded-scoring-design.md`, change the status line:

```markdown
**Status:** implemented 2026-07-20 — see `docs/superpowers/plans/2026-07-20-level-banded-scoring.md`
```

- [ ] **Step 7: Run everything one last time**

Run from the repo root: `make test`
Then: `cd frontend && npm test -- --run && npm run build`
Expected: PASS on all three.

- [ ] **Step 8: Commit**

```bash
git add backend/scripts/seed_demo_data.py frontend/src/features/meets/MeetForm.tsx CLAUDE.md docs/superpowers/specs/2026-07-20-level-banded-scoring-design.md
git commit -m "docs: document the three scoring bands and fix medal-cutoff copy"
```

---

## Notes for the implementer

**The `_routine`/`_entry` test helpers in `test_scoring.py` now carry a level.** They default to `Level.senior` (band 8+) so that every pre-existing worked example keeps testing the full FIG path unchanged. When you add a band-specific test, pass the level explicitly.

**Router tests share one transaction** — a router's `db.rollback()` on the 409 path undoes earlier commits in the same test. Keep each new router test to a single write-path assertion, as the existing tests do.

**Existing data needs no backfill.** Level 4–7 routines currently hold only `execution` marks, which stay legal (merely incomplete). Level 1–3 routines holding `execution` marks are now ignored by `compute_routine_score` rather than mis-scored — that is why Task 3 forces D/A/E to zero at that band instead of summing whatever happens to be present.

**Do not "fix" the DB judge asymmetry.** Levels 4–7 have two `difficulty_body` judges; level 8+ has one `difficulty_body` and one `difficulty_apparatus`. This is confirmed correct.
