# Age Groups u13/u15/o15 + Level 4+ Roster Import

**Date:** 2026-07-21
**Status:** Approved design, pending implementation plan

## Context

A second roster for the same upcoming event, `bulkupload/rhythmic_importer_l4_up.csv`
(72 rows, levels 4 through senior), cannot be imported by `scripts/import_roster.py`
(shipped in PR #12). Three things block it, and one of them is not what it first looked
like.

Profiling the file:

| Column | Finding |
|---|---|
| `age_group` | Uses `u13`, `u15`, `o15` — **none exist in the `AgeGroup` enum**. Also `u9`–`u12`, `u14`, `o14`, which do. 2 rows blank. |
| `date_of_birth` | **Blank on all 72 rows.** |
| `district_name` | Blank on 69 of 72. |
| `club_name` | 7 clubs; `Maties` is new (3 rows, and those 3 carry `Cape Winelands`). |
| `gsa_number` | Present on all 72, all unique, none overlapping the level 1–3 roster. |
| `ethnicity` | Blank on all 72 — maps to NULL by existing design. |
| `level` | `level_4`–`level_10` and `senior`. **All already exist and are already banded.** |

No duplicate `(first_name, last_name)` within the file, and no name overlap with the
level 1–3 roster.

`Level` and `app/scoring.py` need no change: `senior` is already in
`_BAND_8_PLUS_LEVELS`, and every other level in this file is banded.

## Decisions

| Decision | Choice |
|---|---|
| Missing age groups | Add `u13`, `u15`, `o15` via `ALTER TYPE ... ADD VALUE`, positioned |
| Enum ordering | **Do not** recreate the type to "clean up" `o11`'s position |
| Blank `date_of_birth` | Valid → `None`. A non-blank unparseable value stays an error |
| Age vs age group | **No validation, ever.** Age group is not derived from date of birth |
| Blank `district_name` | Derived from the club via `CLUB_ABBREVIATIONS`; ambiguous → error |
| Blank `age_group` (2 rows) | Stays an error — fixed by hand in the source file |
| New club | `("Cape Winelands", "Maties"): "MATIES"` |
| `downgrade()` | Documented no-op, per the existing age-group migration |

## Age group is not a function of date of birth

Recorded because it is the single most likely thing for a future contributor — or a future
Claude — to get wrong, and because an earlier draft of this design got it wrong.

`MeetEntry.age_group` is a **competition band assigned per entry**, not a fact derived from
the gymnast's birthday. Nothing may validate one against the other. This is why 72 gymnasts
arriving with no date of birth has **no** effect on competitive correctness — it is purely
an identity-matching concern (see below).

It also explains the enum's ordering kink. These bands are not rungs on one ladder:
`o11` is the top band for levels 1–3, `o14`/`o15` are top bands further up. `o11` ("12 and
over") and `u12` ("under 12") are complementary halves of one split, not consecutive
values. **There is no correct total order**, which is exactly why reordering the type buys
nothing.

## Enum change

New declaration order in `app/models.py`:

```
u7  u8  u9  u10  u11  o11  u12  u13  u14  u15  o14  o15
```

Migration, hand-written (autogenerate does not detect new values on an existing enum):

```python
op.execute("ALTER TYPE agegroup ADD VALUE IF NOT EXISTS 'under_13' AFTER 'under_12'")
op.execute("ALTER TYPE agegroup ADD VALUE IF NOT EXISTS 'under_15' AFTER 'under_14'")
op.execute("ALTER TYPE agegroup ADD VALUE IF NOT EXISTS 'over_15'  AFTER 'over_14'")
```

Labels are enum **member names** (`under_13`), not values (`u13`) — that is what Postgres
stores. `meet_entries.age_group` is the only column of this type (verified against
`pg_attribute`, not just the ORM).

**Rejected: recreating the type in a "clean" order.** It was briefly chosen on the grounds
that the database is disposable, then dropped: cheaper does not mean worthwhile. Nothing in
the backend sorts by `age_group` — the declaration order's only consumer is the dropdown
sequence in `frontend/src/lib/domain.ts` — and per the section above there is no
semantically correct order to move to. The change would have swapped one arbitrary order
for another while coupling a type recreation to the roster import you need before the event.

`downgrade()` is a deliberate no-op: Postgres cannot drop enum values, and a downgrade that
fails precisely when it is needed is not reversibility. Same reasoning as the
`a22c63eaf9c0` migration.

## Importer changes

### Blank date of birth

`_parse_row` currently treats an unparseable `date_of_birth` as fatal to the row. Blank must
now be valid and yield `None`, while a non-blank unparseable value stays an error. Because
the existing "drop the row" test keys on `date_of_birth is None`, it needs a separate flag
for *present but unparseable* rather than reusing `None` for both states.

`RosterRow.date_of_birth` becomes `date | None`; `identity` becomes
`tuple[str, str, date | None]`.

Consequence to document in the module docstring: with a NULL date of birth,
`uq_gymnast_identity` stops constraining — Postgres treats NULLs as distinct in a unique
index, so unlimited `(name, name, NULL)` rows are legal. **The GSA number becomes the only
thing preventing duplicate people.** All 72 rows have unique ones, so this file is safe;
the exposure is a future hand-entered gymnast with neither.

The report gains one line so this is not invisible:

```
72 gymnasts have no date of birth (matched by GSA number only)
```

One thing verified rather than assumed: SQLAlchemy renders `Gymnast.date_of_birth == None`
as `IS NULL`, not as `= NULL`, so `_find_gymnast`'s identity fallback keeps working with a
null date and needs no change. Worth a comment at that line, because the equivalent raw SQL
would silently match nothing.

### Blank district derived from the club

A module-scope index built **from** `CLUB_ABBREVIATIONS`, so the two cannot drift:

```python
DISTRICTS_BY_CLUB: dict[str, set[str]] = {}
for district, club in CLUB_ABBREVIATIONS:
    DISTRICTS_BY_CLUB.setdefault(club, set()).add(district)
```

When `district_name` is blank:

| Club resolves to | Behaviour |
|---|---|
| exactly one district | derive it, then continue into the existing checks |
| two or more | error: ambiguous, name the districts, tell the operator to put it in the CSV |
| unknown club | the existing paste-ready "unknown club" error only — **not** also a confusing `unknown district ''` |

A district that *is* supplied must still form a known `(district, club)` pair, unchanged.

This is a lookup in a table we maintain, not inference from the data. The `(district, club)`
keying exists precisely because club names are only unique per district, so ambiguity is
detected rather than guessed at.

### New club

`("Cape Winelands", "Maties"): "MATIES"`.

## Frontend

`AGE_GROUPS` in `frontend/src/lib/domain.ts` gains the three values in the same order, and
its comment is updated — it currently claims "two bandings coexist", which this roster
disproves. Then `make types` to regenerate `frontend/src/api/schema.d.ts`.

Existing frontend fixtures use `o14`, which stays valid.

## Testing

- `AgeGroup` has 12 members in the expected order.
- The existing `test_meet_entry.py::...` assertion that the stored Postgres enum order
  equals `[member.name for member in AgeGroup]` covers migration/model drift for free — it
  must still pass after the migration.
- Blank `date_of_birth` parses to `None` and imports; the gymnast row is created.
- A non-blank unparseable `date_of_birth` is still an error.
- Blank district with a club in exactly one district derives that district.
- Blank district with a club in two districts is an ambiguity error.
- Blank district with an unknown club reports the club, and does not also report an empty
  district.
- `Maties` resolves to `MATIES` under Cape Winelands.

All of the above use synthetic rows or `tmp_path` CSVs. **No test may read
`bulkupload/`** — it is gitignored real data about minors, so a test depending on it would
fail for anyone else and must never be written (see the roster import spec).

Verifying against the actual 72-row file is therefore a **manual step**, not a test: after
the 2 blank `age_group` cells are fixed by hand, a dry run must report 0 errors and leave
the database unchanged. Record the counts in the implementation report.

## Out of scope

- Any validation of `age_group` against `date_of_birth` — see the section above.
- Backfilling the missing dates of birth.
- Meet entries and routines for either roster (still pass 2, still blocked on bib numbers).
- Recreating the enum type in a different order.
