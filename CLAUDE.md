# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Rhytmiq: a FIG-compliant API for managing rhythmic gymnastics meets — districts, clubs,
coaches, gymnasts, groups, meets, meet entries, routines, and routine profiles. FastAPI +
Pydantic v2 + SQLAlchemy 2.0, SQLite for local dev/tests. All code lives under `backend/`.

## Commands

All commands run from `backend/`.

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

The SQLite schema is created automatically on startup via `app/db.py:init_db`; there is no
migration step for local dev (alembic is a dependency but not yet wired up).

## Architecture

- `app/main.py` — FastAPI app, registers one router per resource.
- `app/db.py` — engine/session (`sqlite:///./test.db`), `get_db` FastAPI dependency, `lifespan`
  that calls `init_db()`.
- `app/models.py` — all SQLAlchemy ORM models and enums in one file.
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
- Every resource listed above (`District` through `RoutineProfile`) now has a full
  model/schema/router. `Group` and `Routine` were the last two to get routers.
