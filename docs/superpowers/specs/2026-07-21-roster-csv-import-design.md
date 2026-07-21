# Roster CSV Import — Districts, Clubs, Gymnasts

**Date:** 2026-07-21
**Status:** Approved design, pending implementation plan

## Context

A real roster of 93 participant rows for an upcoming Western Cape meet arrived as
`bulkupload/rhythmiq_import_participants.csv`. Every gymnast, club and district in it is
new to the database — the only populated data so far is `scripts/seed_demo_data.py`
output. Entering 90 people through `/docs` or the admin console is not viable.

The CSV's grain does not match any single table. Each row is an *event entry*, which the
schema splits three ways: `Gymnast` (the person), `MeetEntry` (unique on
`meet_id, gymnast_id` — one per gymnast per meet), and `Routine` (which is where
`apparatus` actually lives). Three gymnasts appear twice in the file, once for Clubs and
once for Ribbon, so 93 rows describe **90 distinct gymnasts**.

These two datasets also have different lifecycles. The roster is reference data that stays
largely static year to year — gymnasts compete in many meets, and not every gymnast enters
every meet. Meet entries are per-meet, and are additionally blocked on bib numbers, which
live in a separate and badly formatted spreadsheet. Coupling them would tie an annual job
to a per-meet one.

**This spec covers pass 1 only: districts, clubs and gymnasts.** Meet entries and routines
are pass 2, specced separately once the bib-number source is usable.

## Decisions

| Decision | Choice |
|---|---|
| Scope | `District`, `Club`, `Gymnast` only. No `MeetEntry`, no `Routine` |
| Location | `backend/scripts/import_roster.py` (renamed from the empty `bulk_insert.py`) |
| Interface | CLI script following `seed_demo_data.py` conventions; **dry run is the default**, `--commit` required to write |
| Gymnast match key | `gsa_number` first, falling back to `(first_name, last_name, date_of_birth)` |
| On conflict | Report every differing field, change nothing |
| Abbreviations | Hardcoded tables in the module, keyed by district name and by **`(district, club)`** |
| Unknown district/club | Abort the run with a paste-ready table line — never auto-generate a code |
| `country_code` | Left `NULL` — the CSV has no country column |
| Blank `ethnicity` | `NULL`, never an error |
| `age_group` vs `date_of_birth` | Deliberately not validated |
| Transaction | One transaction, one commit at the end |

## Source data

93 rows, UTF-8 (8 rows contain non-ASCII names such as "Ané"). Columns:

```
first_name, last_name, date_of_birth, gsa_number, ethnicity, club_name,
district_name, level, age_group, apparatus, needs_manual_split,
entry_fee_paid, raw_event
```

Pass 1 persists only `first_name`, `last_name`, `date_of_birth`, `gsa_number`,
`ethnicity`, and the `club_name`/`district_name` it resolves to a `club_id`. Of the rest,
`level` and `age_group` are **validated but not written**, while `apparatus`,
`needs_manual_split`, `entry_fee_paid` and `raw_event` are **ignored entirely** — they are
not in `REQUIRED_COLUMNS` and are never read. All six are pass-2 input and
must stay in the file.

Profile of the current file:

- 3 districts, 6 clubs, each club under exactly one district, no blank cells
- Levels 1–3 only; age groups u7, u8, u9, u10, u11, o11
- All 93 rows carry a GSA number; 3 numbers appear twice (the three two-row gymnasts)
- Ethnicity values are `white`, `coloured`, `black`, `indian` — all valid enum members
- No `first_name` shorter than 3 characters, so `ck_gymnast_first_name_nonempty` is safe

## Level → apparatus (recorded for pass 2, not implemented here)

Confirmed domain knowledge, currently absent from the codebase — nothing constrains which
apparatus a level competes:

| Level | Apparatus |
|---|---|
| 1 | Freehand, Ball |
| 2 | Freehand, Hoop |
| 3 | Clubs, Ribbon |

This makes `needs_manual_split` redundant: the 87 "All Apparatus" rows expand to their
level's pair, and the 6 single-apparatus rows are 3 gymnasts × {clubs, ribbon} — the
*complete* Level 3 set. Every gymnast in this file competes their full set, so pass 2 will
produce a uniform 90 entries and 180 routines.

Pass 2 should still expand faithfully rather than deriving purely from level: a
`needs_manual_split=True` row expands to the level's full set, a single-apparatus row to
just that apparatus, then union per gymnast. Deriving from level alone would fabricate a
routine for a gymnast who genuinely entered only one apparatus.

Levels 4+ are not yet defined and are not needed by this spec. When the table is
implemented it belongs beside the band table in `app/scoring.py`, not in the importer —
`rank_all_around` currently reports `routines_counted` with no idea what a *complete*
all-around is, and the levels 1–3 "max 26" medal cutoff depends on the same knowledge.

## Abbreviation tables

`District.abbreviation` and `Club.abbreviation` are both `String(10)`, `NOT NULL` and
unique, and the CSV supplies neither. With 3 districts and 6 clubs, a hand-maintained
table beats any slugging heuristic.

```python
DISTRICT_ABBREVIATIONS = {
    "Cape Winelands": "CWDM",
    "West Coast District": "WCD",
    "Eden": "EDEN",
}

CLUB_ABBREVIATIONS = {
    ("Cape Winelands", "Fynbos Gymnastics Club"): "FYN",
    ("Cape Winelands", "Infinity Rhythmic Gymnastics"): "INF",
    ("Cape Winelands", "Van Der Stel"): "VDS",
    ("Cape Winelands", "Ikaya Primary School"): "IKAYA",
    ("West Coast District", "Reach Rhythmic Gymnastics"): "REACH",
    ("Eden", "Zest"): "ZEST",
}
```

`CLUB_ABBREVIATIONS` is keyed by `(district, club)` rather than club name because club
identity in the schema is per-district: both `uq_club_name` and `uq_club_abbreviation` are
scoped by `district_id`, and the `Club` docstring explicitly allows two districts to share
a name or abbreviation. A club-name-keyed table would attach gymnasts of a second
district's same-named club to the first district's club, and no constraint would catch it
because both rows are individually legal.

An unrecognised district or club aborts the run before any write, printing the line to
add:

```
Unknown club: 'Boland Gymnastics' (district 'Cape Winelands')
Add to CLUB_ABBREVIATIONS in scripts/import_roster.py:
    ("Cape Winelands", "Boland Gymnastics"): "BOLAND",
```

This is the importer's single maintenance point. A CSV containing later levels needs no
code change at all — nothing pass 1 persists depends on level, and both the `Level` and
`AgeGroup` enums already span the full range. Only new clubs or districts require an edit.

## Pipeline

Four phases. Nothing is written until every check passes.

### 1. Parse and validate rows

Read as UTF-8. For every row, check:

- all expected columns present
- `date_of_birth` parses as ISO `YYYY-MM-DD` and is not in the future
  (mirrors `ck_gymnast_date_of_birth_valid`)
- `first_name` longer than 2 characters (mirrors `ck_gymnast_first_name_nonempty`)
- `last_name` non-blank
- `level` and `age_group` are valid `Level` / `AgeGroup` members
- `ethnicity` is a valid `Ethnicity` member, **or blank → `None`**
- `club_name` and `district_name` non-blank and present in the abbreviation tables

Errors accumulate across all rows and are reported together with row numbers. Fixing a
spreadsheet one error per run is miserable; the run aborts once, with the full list.

Blank `ethnicity` maps to `NULL`, never `prefer_not_to_say`. The `Ethnicity` docstring
draws this line deliberately: `NULL` means the question was never asked, `prefer_not_to_say`
means the gymnast was asked and declined. A blank cell is the former.

`age_group` is **not** cross-checked against `date_of_birth`. Age banding is relative to a
competition date the roster file does not carry, and the two coexisting bandings (u7–o11
and u12/u14/o14) make "correct" ambiguous. Guessing here would reject valid rows.

### 2. Cross-row consistency

Checks that a single row cannot reveal:

- a club name must not appear under two different districts within one file
- one `gsa_number` must not carry two different `(first_name, last_name, date_of_birth)`
- one identity must not carry two different `gsa_number` values

The current file passes all three. A future one may not, and each failure would otherwise
surface as a confusing mid-run `IntegrityError`.

### 3. Resolve reference data

Get-or-create `District` by name, then `Club` by `(district_id, name)`, taking
abbreviations from the tables. Existing rows are reused as-is; a district or club whose
stored abbreviation differs from the table is reported as a difference, not updated.

### 4. Resolve gymnasts

For each of the 90 distinct gymnasts:

1. Look up by `gsa_number` when present.
2. Fall back to `(first_name, last_name, date_of_birth)`.
3. **Found** — compare `first_name`, `last_name`, `date_of_birth`, `ethnicity`,
   `gsa_number` and `club_id`; record every difference; write nothing.
4. **Not found** — insert, with `country_code` and `group_id` left `NULL`.

GSA-first matching is what makes year two painless. `Gymnast` carries two competing unique
keys — `uq_gymnast_identity` on `(first_name, last_name, date_of_birth)` and
`uq_gymnast_gsa_number` — and they disagree the moment a name spelling or DOB is corrected
in the CSV. Identity-first matching would find nothing, attempt an insert, and collide on
the GSA constraint mid-run. The GSA number is the real membership ID, so it is the
stabler key.

Reporting rather than updating means a stale or wrong CSV can never damage hand-corrected
data. The expected real-world cost is club transfers, which must be applied by hand. If
the difference report becomes routinely long, that is the signal to add an opt-in
`--apply-changes` flag — not before.

## Output

```
Districts:   3 (0 created, 3 existing)
Clubs:       6 (2 created, 4 existing)
Gymnasts:   90 (88 created, 2 existing)

2 differences found (nothing changed):
  Lia Hamman (GSA 31392)  club: Fynbos Gymnastics Club -> Van Der Stel
  Pippa Benade (GSA 54251)  ethnicity: NULL -> white

DRY RUN -- nothing written. Re-run with --commit to apply.
```

With `--commit`, the final line becomes a confirmation that the transaction committed.

## Structure

```
backend/scripts/import_roster.py
    DISTRICT_ABBREVIATIONS, CLUB_ABBREVIATIONS
    RosterRow                                          # frozen; .identity, .match_key
    ImportReport                                       # seven list[str] fields
    parse_csv(path) -> tuple[list[RosterRow], list[str]]   # I/O + per-row validation
    check_consistency(rows) -> list[str]                   # cross-row rules
    import_roster(rows, session) -> ImportReport           # flushes; never commits
    format_report(report, *, committed) -> str             # the printed summary
    main() -> int                                          # argparse, SessionLocal,
                                                           # commit/rollback, exit code
```

`parse_csv` returns rows *and* errors; the rows are only meaningful when the error list
is empty, and `main()` aborts before opening a session if it is not.

`import_roster` takes already-parsed rows and a session and returns a report without
committing, so tests drive it through the existing `db_session` fixture with small
synthetic row lists. Never committing is the load-bearing property: it is what lets
`main()` run the real inserts and then roll back, making the dry run a genuine
transaction rather than a simulation.

`ImportReport` holds only strings, never ORM objects, so `format_report` is safe to call
*after* the commit or rollback has expired every instance — which is the order `main()`
uses, so the closing "Committed." line can never be printed before the database agrees.

`main()` owns the `try` / `commit` / `except` / `rollback` / `finally close` shape that
`seed_demo_data.py` established, and rolls back instead of committing on a dry run.

## Testing

New `backend/test/test_scripts/test_import_roster.py`:

- cold start creates districts, clubs and gymnasts
- **re-running against the same data is a no-op** — no new rows, no differences
- a renamed gymnast with an unchanged GSA number matches the existing row
- a gymnast with a blank GSA number matches on identity
- a differing field is reported and not written
- validation errors are collected across rows and abort before any write
- a club under two districts in one file is rejected
- one GSA number with two identities is rejected
- one identity with two GSA numbers is rejected
- an unknown district or club aborts with the paste-ready message
- blank ethnicity stores `NULL`, not `prefer_not_to_say`
- one round-trip test parsing an actual small CSV fixture, covering UTF-8 names

## Out of scope

- Meet entries and routines (pass 2, blocked on bib numbers)
- The level → apparatus table in `app/scoring.py` (recorded above, implemented with pass 2)
- Coaches, groups and routine profiles — absent from the CSV
- Updating existing gymnasts (reported only, by decision)
- An HTTP upload endpoint — this is an operator-run script
