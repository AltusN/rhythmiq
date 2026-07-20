# Age groups: add u7, u9, u11, o11

Add four values to the `AgeGroup` enum. Purely additive — no existing value is
removed or renamed.

## Motivation

The competition bandings in use need u7/u8/u9/u10/u11/o11. `u8` and `u10` already
exist, so only `u7`, `u9`, `u11` and `o11` are new. The older `u12`/`u14`/`o14`
bandings stay: they are in live data (`under_10` x3, `under_8` x1, `under_12` x1
at time of writing) and remain selectable.

## Value list and ordering

The enum ends up as, in this exact order:

```
u7, u8, u9, u10, u11, o11, u12, u14, o14
```

Order matters. Postgres sorts an enum by its **definition order**, not
alphabetically, and the existing order is already semantically meaningful. If the
new values were simply appended, sorting would yield
`... o14, u7, u9, u11, o11` — nonsense. Each new value is therefore positioned
explicitly, and the Python class is written in the same order so the source reads
the way the data sorts.

`o11` sits after `u11` and before `u12`. It overlaps `u12`/`u14`/`o14`
semantically — two banding schemes coexist by design, and the dropdowns show all
nine in age order.

## Model

`app/models.py`:

```python
class AgeGroup(StrEnum):
    under_7 = "u7"      # new
    under_8 = "u8"
    under_9 = "u9"      # new
    under_10 = "u10"
    under_11 = "u11"    # new
    over_11 = "o11"     # new
    under_12 = "u12"
    under_14 = "u14"
    over_14 = "o14"
```

## Migration

Hand-written. Created with `alembic revision -m "..."` **without**
`--autogenerate`, which does not detect new values on an existing enum (see
`CLAUDE.md`).

```python
op.execute("ALTER TYPE agegroup ADD VALUE IF NOT EXISTS 'under_7' BEFORE 'under_8'")
op.execute("ALTER TYPE agegroup ADD VALUE IF NOT EXISTS 'under_9' AFTER 'under_8'")
op.execute("ALTER TYPE agegroup ADD VALUE IF NOT EXISTS 'under_11' AFTER 'under_10'")
op.execute("ALTER TYPE agegroup ADD VALUE IF NOT EXISTS 'over_11' AFTER 'under_11'")
```

The labels are the enum **member names** (`under_8`), not the values (`u8`) —
verified against `pg_enum` rather than assumed.

Postgres 17.10 permits `ALTER TYPE ... ADD VALUE` inside a transaction, so this
runs under Alembic's normal transaction. The new values cannot be *used* in the
same transaction, which this migration does not do.

`downgrade()` is a documented **no-op**. Postgres cannot drop an enum value; a
real reversal would mean recreating the type and rewriting every column that uses
it. An honest no-op beats a clever downgrade that could fail halfway. This
deliberately differs from the reversible `ethnicity` migration, which created a
new type rather than extending one.

## Frontend

One line at `frontend/src/lib/domain.ts:7`:

```ts
export const AGE_GROUPS: AgeGroup[] = ["u7","u8","u9","u10","u11","o11","u12","u14","o14"];
```

`AGE_GROUPS` is the single source consumed by `StandingsPage`,
`EntryCreateForm` and `CompetitorList`, so all three update from this one edit.
`make types` regenerates the union in `schema.d.ts`.

## Tests

- Model: each new value round-trips through a persisted `MeetEntry`.
- Model: the stored enum order matches the intended order (guards the
  `BEFORE`/`AFTER` positioning, which is the part most likely to be got wrong).
- Frontend: the age-group dropdowns offer all nine values.

Nothing in the codebase asserts full enum membership (checked: 82 references, none
brittle), so no existing test needs changing.

## Out of scope

- Removing or renaming `u12`/`u14`/`o14`
- Any rule about which banding a given meet should use
- Validating age against `date_of_birth`
