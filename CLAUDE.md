# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Rhytmiq: a FIG-compliant API for managing rhythmic gymnastics meets — districts, clubs,
coaches, gymnasts, groups, meets, meet entries, routines, routine profiles, judges, judge
scores, and itemized penalty records. FastAPI + Pydantic v2 + SQLAlchemy 2.0 + Alembic,
backed by a dockerized Postgres. All code lives under `backend/`. The test suite runs
against that same dockerized Postgres, with each test isolated via a rolled-back
transaction (see `test/conftest.py`).

## Commands

From the **repo root** (needs `.env`, copied from `.env.example`):

```bash
make dev                      # docker compose up -d + alembic upgrade head
make migration name="..."     # alembic revision --autogenerate
make test                     # migrate the test db + run pytest
make seed                     # populate demo data across every table
make reset                    # wipe the local Postgres volume, start fresh
```

All other commands run from `backend/`.

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

uvicorn app.main:app --reload   # serve at http://127.0.0.1:8000 (docs at /docs, /redoc)

pytest                           # run all tests
pytest test/test_routers/test_meet_router.py   # single file
pytest test/test_routers/test_meet_router.py::test_create_meet_success   # single test

ruff check .                    # lint
ruff format .                   # format
```

`pre-commit` runs `ruff --fix` + `ruff format` on commit but isn't in `requirements.txt` —
install separately and run `pre-commit install` once.

The schema is never auto-created on app startup — `alembic upgrade head` is the only way to
build or update it. Adding a new value to an existing enum (e.g. a new `Level`) is not
detected by autogenerate and needs a hand-written `op.execute("ALTER TYPE ... ADD VALUE ...")`
migration.

## Architecture

- `app/main.py` — FastAPI app, registers one router per resource.
- `app/db.py` — engine/session (Postgres via `POSTGRESQL_DATABASE_URL`), `get_db` FastAPI
  dependency, `lifespan` (disposes the engine on shutdown; schema creation is Alembic's job).
- `app/models.py` — all SQLAlchemy ORM models and enums in one file.
- `migrations/` — Alembic environment; `env.py` sources `sqlalchemy.url` from
  `app.db.POSTGRESQL_DATABASE_URL` and `target_metadata` from `app.models.Base`, so both stay
  in sync with the app automatically. Generated migrations live under `migrations/versions/`.
- `scripts/seed_demo_data.py` — populates a freshly migrated database with demo data across
  every table (`make seed`); not idempotent, pair with `make reset` to start over.
- `app/routers/<resource>.py` — one router per resource, all following the same CRUD shape.
- `app/schemas/<resource>.py` — Pydantic `*Create` / `*Update` / `*Read` models per resource.
- `test/conftest.py` — top-level `db_session` fixture (raw SQLAlchemy session, FKs pragma on)
  plus `make_*` factory helpers for every model, used directly by model/schema tests.
- `test/test_routers/conftest.py` — separate `db_session` + `client` fixtures that override
  `get_db` so router tests exercise the full FastAPI request/response pipeline (not just the
  handler function).
- Test layout mirrors app layout: `test_models/`, `test_schemas/`, `test_routers/`.

### Router conventions (mirrored across every resource)

Every resource router follows: `POST /`, `GET /`, `GET /{id}`, `PATCH /{id}`, `DELETE /{id}`.

- **Create**: pre-check any non-null FK references with `db.get(...)` → 404 if missing, before
  constructing the model instance from `payload.model_dump()`.
- **Update**: build the ORM instance update via `payload.model_dump(exclude_unset=True)`, only
  pre-checking FKs that appear in the update payload (not the full schema).
- **Write path**: `db.add()` / mutate → `db.flush()` → `db.commit()` → `db.refresh()`, wrapped
  in `try/except IntegrityError` → `db.rollback()` + `HTTPException(409)`.
- **Delete**: `db.get()` → 404 if missing → `db.delete()` → `db.commit()`.
- **List filters**: optional query params map directly to `.filter(Model.col == value)`.
- Router docstrings ("Design notes") explain resource-specific quirks (see `meet.py`,
  `meet_entry.py`) — read them before modifying that router, and add to them when the logic
  is non-obvious.

### Domain model specifics

- `Meet.status` transitions are forward-only (`draft → scheduled → in_progress → completed`),
  enforced in `routers/meet.py` via `ALLOWED_STATUS_TRANSITIONS`; any status can go to
  `cancelled`; sending the current status is a no-op, not an error.
- `Meet` PATCH date validation: the Pydantic model_validator on `MeetUpdate` only fires when
  both dates are present in one payload; when only one date is sent, the router validates the
  incoming value against the stored counterpart (`_validate_partial_dates`).
- `MeetEntry` requires exactly one of `gymnast_id`/`group_id` — enforced both by a Pydantic
  `model_validator` on `MeetEntryCreate` and by a DB `CheckConstraint`. FK fields on
  `MeetEntry` are not updatable after creation (delete + recreate instead).
- `RoutineProfile` follows the same exactly-one-of-`gymnast_id`/`group_id` pattern as
  `MeetEntry` (model_validator + CheckConstraint), scoped further by a `UniqueConstraint` on
  (owner, apparatus, level). Only `music_url`/`choreography_notes` are updatable after
  creation. `Routine.music_url` resolves it live (by gymnast/group + apparatus + level, no
  meet linkage) — deliberately not snapshotted per meet.
- Deletion semantics vary by relationship: `Gymnast` deletes cascade to `MeetEntry`/`Routine`;
  `Meet` deletes also cascade, but are rejected (409) while `in_progress` or `completed` —
  a completed meet is the historical record of who competed, so it can't be silently wiped.
  `Club`/`Group`/`District` deletes are rejected (409) via `RESTRICT` FKs when dependents exist.
- `Routine.penalty` is a directly-settable aggregate for the common case (most routines
  have at most one penalty), but once a routine has any itemized `PenaltyRecord`s
  (`routers/penalty_record.py`), direct `PATCH` of `penalty` is rejected (409) — it can
  only change via the itemized records from then on. Every `PenaltyRecord`
  POST/PATCH/DELETE re-syncs `Routine.penalty` to the sum of that routine's records
  (`_resync_routine_penalty`), so the aggregate and the itemized total can never drift
  apart. The first record added to a routine with a manually-set `penalty` overwrites
  it, rather than merging — itemization takes over, it doesn't add to what was there.
- Every resource listed above (`District` through `PenaltyRecord`) now has a full
  model/schema/router. `Judge`, `JudgeScore`, and `PenaltyRecord` were the last three to
  get routers.
- **Results/reporting** (`routers/results.py`, read-only, no model of its own):
  `GET /meets/{id}/standings?apparatus=...` ranks routines within one (level, age_group,
  apparatus) slice; `GET /meets/{id}/all-around?...` sums each entry's routine totals
  across apparatus within one (level, age_group) slice and ranks those sums. Both are
  computed live via `rank_apparatus`/`rank_all_around` (`app/scoring.py`) — never
  snapshotted, same philosophy as `Routine.music_url`. Ties break by highest total
  Execution (FIG Technical Regulations), then share a rank (competition ranking:
  1,2,2,4). `provisional` is `true` unless `meet.status == completed`. All-around sums
  are not required to be complete — a competitor missing an apparatus is still ranked on
  their partial total, with `routines_counted` surfacing that it's partial. Deferred:
  district/club team scores, CSV export, and any snapshotted official-results record.
