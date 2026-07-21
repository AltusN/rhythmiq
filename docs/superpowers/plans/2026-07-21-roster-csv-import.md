# Roster CSV Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A re-runnable CLI script that imports a participant CSV into `District`, `Club` and `Gymnast`, creating missing reference data and reporting — never applying — differences on gymnasts that already exist.

**Architecture:** Four phases with a hard fail-fast boundary: `parse_csv` (I/O + per-row validation) → `check_consistency` (cross-row rules) → `import_roster` (pure, session-taking, never commits) → `main` (argparse, `SessionLocal`, commit or rollback). Splitting I/O from the DB work lets every DB test drive `import_roster` directly with synthetic `RosterRow` lists through the existing `db_session` fixture.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 ORM, stdlib `csv` / `argparse` / `dataclasses`, pytest.

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-07-21-roster-csv-import-design.md`. Read it before starting.
- Scope is `District`, `Club`, `Gymnast` **only**. Do not create `MeetEntry` or `Routine` — that is a separate later pass.
- All commands run from `backend/` with the venv active: `cd backend && source .venv/bin/activate`.
- The test DB must be running: from the **repo root**, `make dev` (docker compose + alembic upgrade). Tests fail with a connection error otherwise.
- `ruff` line-length is 100, `target-version = "py312"`. Run `ruff check . && ruff format .` before every commit.
- Commit subjects **must** start with `feat:` / `fix:` / `chore:` / `docs:` / `test:`.
- The file `backend/scripts/import_roster.py` already exists and is **empty**. Do not create it; write into it.
- Never modify `bulkupload/rhythmiq_import_participants.csv`. It is real participant data.
- `parse_csv` returns `(rows, errors)`. **`rows` is only meaningful when `errors` is empty** — a row failing name or ethnicity validation is still returned. `main()` aborts on any error, so partial rows never reach `import_roster`.

## File structure

| File | Responsibility |
|---|---|
| `backend/scripts/import_roster.py` (exists, empty) | Everything: abbreviation tables, `RosterRow`, `parse_csv`, `check_consistency`, `ImportReport`, `import_roster`, `format_report`, `main`. ~250 lines — one file matches `seed_demo_data.py`'s single-file convention. |
| `backend/test/test_scripts/test_import_roster.py` (create) | All tests. No `__init__.py` needed — `test/test_models/` and friends have none. |
| `backend/test/test_scripts/fixtures/roster_sample.csv` (create) | Tiny CSV fixture for the parse round-trip, including a UTF-8 name. |
| `CLAUDE.md` (modify) | One bullet documenting the script, next to the `seed_demo_data.py` bullet. |

## Domain facts you will need

- `District`: `name` (unique), `abbreviation` (`String(10)`, NOT NULL, unique globally).
- `Club`: `district_id`, `name`, `abbreviation` — **both uniques are scoped per district** (`uq_club_name`, `uq_club_abbreviation`). This is why `CLUB_ABBREVIATIONS` is keyed by `(district, club)` and not by club name.
- `Gymnast`: two competing uniques — `uq_gymnast_identity` on `(first_name, last_name, date_of_birth)` and `uq_gymnast_gsa_number` on `gsa_number`. Match on GSA first, identity second.
- `Gymnast` check constraints: `length(first_name) > 2`, `date_of_birth <= current_date`.
- `Ethnicity` blank in CSV → `None`, **never** `Ethnicity.prefer_not_to_say`. NULL means "never asked"; `prefer_not_to_say` means "asked and declined".
- `Level`, `AgeGroup`, `Ethnicity` are `StrEnum`s, so `Level("level_1")` and `AgeGroup("u9")` construct directly and raise `ValueError` on a bad value.
- The real CSV has 93 rows, 3 districts, 6 clubs, and **90 distinct gymnasts** (3 gymnasts occupy 2 rows each).
- `age_group` is deliberately **not** cross-checked against `date_of_birth`. Age banding is relative to a competition date the roster file does not carry, and the two coexisting bandings (u7–o11 and u12/u14/o14) make "correct" ambiguous. Do not add this check.

---

### Task 1: Row parsing and validation

**Files:**
- Modify: `backend/scripts/import_roster.py` (currently empty)
- Create: `backend/test/test_scripts/test_import_roster.py`
- Create: `backend/test/test_scripts/fixtures/roster_sample.csv`

**Interfaces:**
- Consumes: `app.models.AgeGroup`, `Ethnicity`, `Level`.
- Produces:
  - `DISTRICT_ABBREVIATIONS: dict[str, str]`
  - `CLUB_ABBREVIATIONS: dict[tuple[str, str], str]`
  - `RosterRow` — frozen dataclass with `row_number: int`, `first_name: str`, `last_name: str`, `date_of_birth: date`, `gsa_number: str | None`, `ethnicity: Ethnicity | None`, `district_name: str`, `club_name: str`, `level: Level`, `age_group: AgeGroup`; properties `identity -> tuple[str, str, date]` and `match_key -> tuple[str, object]`
  - `parse_csv(path: Path | str) -> tuple[list[RosterRow], list[str]]`

- [ ] **Step 1: Create the CSV fixture**

Create `backend/test/test_scripts/fixtures/roster_sample.csv` (must be UTF-8; the `Ané` row exists to prove encoding handling):

```csv
first_name,last_name,date_of_birth,gsa_number,ethnicity,club_name,district_name,level,age_group,apparatus,needs_manual_split,entry_fee_paid,raw_event
Ané,Alberts,2015-07-15,35112,white,Fynbos Gymnastics Club,Cape Winelands,level_3,u11,,True,False,All Apparatus Level 3 u11
Pippa,Benade,2016-08-23,54251,,Infinity Rhythmic Gymnastics,Cape Winelands,level_3,u11,,True,False,All Apparatus Level 3 u11
Zola,Ntuli,2017-02-11,60001,black,Zest,Eden,level_1,u9,,True,False,All Apparatus Level 1 u9
```

- [ ] **Step 2: Write the failing tests**

Create `backend/test/test_scripts/test_import_roster.py`:

```python
"""
Tests for scripts/import_roster.py.

Split to mirror the script's own phases: parsing/validation and cross-row consistency
are pure and need no database; import_roster gets the db_session fixture.
"""

from datetime import date
from pathlib import Path

from app.models import AgeGroup, Ethnicity, Level
from scripts.import_roster import RosterRow, parse_csv

FIXTURES = Path(__file__).parent / "fixtures"


def make_row(**overrides) -> RosterRow:
    """A valid RosterRow, so each test only states the field it cares about."""
    defaults = dict(
        row_number=2,
        first_name="Anna",
        last_name="Petrov",
        date_of_birth=date(2016, 10, 1),
        gsa_number="10001",
        ethnicity=Ethnicity.white,
        district_name="Eden",
        club_name="Zest",
        level=Level.level_1,
        age_group=AgeGroup.under_9,
    )
    return RosterRow(**{**defaults, **overrides})


def write_csv(tmp_path, body: str) -> Path:
    header = (
        "first_name,last_name,date_of_birth,gsa_number,ethnicity,"
        "club_name,district_name,level,age_group\n"
    )
    path = tmp_path / "roster.csv"
    path.write_text(header + body, encoding="utf-8")
    return path


def test_parses_a_valid_csv():
    rows, errors = parse_csv(FIXTURES / "roster_sample.csv")

    assert errors == []
    assert len(rows) == 3
    assert rows[0].first_name == "Ané"  # UTF-8 survives the round trip
    assert rows[0].date_of_birth == date(2015, 7, 15)
    assert rows[0].ethnicity is Ethnicity.white
    assert rows[0].level is Level.level_3
    assert rows[0].age_group is AgeGroup.under_11
    assert rows[0].row_number == 2  # header is line 1


def test_blank_ethnicity_parses_as_none_not_prefer_not_to_say():
    rows, errors = parse_csv(FIXTURES / "roster_sample.csv")

    assert errors == []
    assert rows[1].first_name == "Pippa"
    assert rows[1].ethnicity is None


def test_collects_every_error_rather_than_stopping_at_the_first(tmp_path):
    path = write_csv(
        tmp_path,
        "Jo,Smith,2016-01-01,1,white,Zest,Eden,level_1,u9\n"
        "Anna,Smith,2099-01-01,2,white,Zest,Eden,level_1,u9\n"
        "Bella,Smith,2016-01-01,3,purple,Zest,Eden,level_1,u9\n",
    )

    rows, errors = parse_csv(path)

    assert len(errors) == 3
    assert "row 2: first_name 'Jo' must be longer than 2 characters" in errors
    assert "row 3: date_of_birth 2099-01-01 is in the future" in errors
    assert "row 4: ethnicity 'purple' is not a valid Ethnicity" in errors


def test_unknown_club_reports_the_line_to_paste(tmp_path):
    path = write_csv(
        tmp_path,
        "Carla,Smith,2016-01-01,4,,Boland Gym,Cape Winelands,level_1,u9\n",
    )

    rows, errors = parse_csv(path)

    assert len(errors) == 1
    assert "unknown club 'Boland Gym' (district 'Cape Winelands')" in errors[0]
    assert '("Cape Winelands", "Boland Gym"): "ABBREV",' in errors[0]


def test_unknown_district_reports_the_line_to_paste(tmp_path):
    path = write_csv(
        tmp_path,
        "Carla,Smith,2016-01-01,4,,Zest,Overberg,level_1,u9\n",
    )

    rows, errors = parse_csv(path)

    # Unknown district also makes the (district, club) pair unknown, hence two errors.
    assert any("unknown district 'Overberg'" in error for error in errors)
    assert any('"Overberg": "ABBREV",' in error for error in errors)


def test_missing_column_aborts_before_reading_any_row(tmp_path):
    path = tmp_path / "roster.csv"
    path.write_text("first_name,last_name\nAnna,Petrov\n", encoding="utf-8")

    rows, errors = parse_csv(path)

    assert rows == []
    assert len(errors) == 1
    assert "missing required column(s)" in errors[0]
    assert "date_of_birth" in errors[0]


def test_blank_gsa_number_parses_as_none(tmp_path):
    path = write_csv(
        tmp_path,
        "Carla,Smith,2016-01-01,,white,Zest,Eden,level_1,u9\n",
    )

    rows, errors = parse_csv(path)

    assert errors == []
    assert rows[0].gsa_number is None


def test_match_key_prefers_gsa_number_and_falls_back_to_identity():
    assert make_row(gsa_number="10001").match_key == ("gsa", "10001")
    assert make_row(gsa_number=None).match_key == (
        "identity",
        ("Anna", "Petrov", date(2016, 10, 1)),
    )
```

- [ ] **Step 3: Run the tests to verify they fail**

```bash
cd backend && source .venv/bin/activate
pytest test/test_scripts/test_import_roster.py -v
```

Expected: collection error — `ImportError: cannot import name 'RosterRow' from 'scripts.import_roster'`.

- [ ] **Step 4: Write the implementation**

Write `backend/scripts/import_roster.py`:

```python
"""
Import a participant roster CSV into districts, clubs and gymnasts.

Pass 1 of a two-pass import (see
docs/superpowers/specs/2026-07-21-roster-csv-import-design.md). The roster is reference
data with its own lifecycle -- gymnasts compete in many meets and the list is largely
static year to year -- so this script deliberately stops at Gymnast. Meet entries and
routines are pass 2, and are blocked on a separate bib-number source.

The CSV's `level`, `age_group`, `apparatus`, `needs_manual_split`, `entry_fee_paid` and
`raw_event` columns are validated but NOT persisted: they are pass-2 input and must stay
in the file.

Dry run is the default; --commit is required to write. A dry run is not a simulation --
it performs the real inserts inside a transaction and rolls back, so constraint
violations surface before you commit.

Usage (from backend/):

    python -m scripts.import_roster ../bulkupload/rhythmiq_import_participants.csv
    python -m scripts.import_roster ../bulkupload/rhythmiq_import_participants.csv --commit
"""

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from app.models import AgeGroup, Ethnicity, Level

# District.abbreviation and Club.abbreviation are NOT NULL and the CSV supplies neither,
# so they are maintained here. An unknown name aborts the run rather than auto-generating
# a code, because a generated abbreviation is wrong in a way nobody notices until it is
# printed on a start list.
DISTRICT_ABBREVIATIONS: dict[str, str] = {
    "Cape Winelands": "CWDM",
    "West Coast District": "WCD",
    "Eden": "EDEN",
}

# Keyed by (district, club), NOT club name alone: uq_club_name and uq_club_abbreviation
# are both scoped by district_id, so two districts may each have a club of the same name.
# A club-name-keyed table would silently attach gymnasts to the other district's club.
CLUB_ABBREVIATIONS: dict[tuple[str, str], str] = {
    ("Cape Winelands", "Fynbos Gymnastics Club"): "FYN",
    ("Cape Winelands", "Infinity Rhythmic Gymnastics"): "INF",
    ("Cape Winelands", "Van Der Stel"): "VDS",
    ("Cape Winelands", "Ikaya Primary School"): "IKAYA",
    ("West Coast District", "Reach Rhythmic Gymnastics"): "REACH",
    ("Eden", "Zest"): "ZEST",
}

REQUIRED_COLUMNS = (
    "first_name",
    "last_name",
    "date_of_birth",
    "gsa_number",
    "ethnicity",
    "club_name",
    "district_name",
    "level",
    "age_group",
)


@dataclass(frozen=True)
class RosterRow:
    """One validated CSV row. row_number is the line in the file, header being line 1."""

    row_number: int
    first_name: str
    last_name: str
    date_of_birth: date
    gsa_number: str | None
    ethnicity: Ethnicity | None
    district_name: str
    club_name: str
    level: Level
    age_group: AgeGroup

    @property
    def identity(self) -> tuple[str, str, date]:
        """The uq_gymnast_identity tuple."""
        return (self.first_name, self.last_name, self.date_of_birth)

    @property
    def match_key(self) -> tuple[str, object]:
        """
        How this row is deduplicated within one file, mirroring how import_roster matches
        against the database: GSA number when present, identity otherwise.
        """
        if self.gsa_number:
            return ("gsa", self.gsa_number)
        return ("identity", self.identity)


def _parse_row(number: int, raw: dict[str, str], errors: list[str]) -> RosterRow | None:
    def field(name: str) -> str:
        return (raw.get(name) or "").strip()

    first_name = field("first_name")
    last_name = field("last_name")
    # Mirrors ck_gymnast_first_name_nonempty, so a bad row is reported here rather than
    # blowing up as an IntegrityError halfway through the insert loop.
    if len(first_name) <= 2:
        errors.append(f"row {number}: first_name {first_name!r} must be longer than 2 characters")
    if not last_name:
        errors.append(f"row {number}: last_name is blank")

    date_of_birth = None
    try:
        date_of_birth = datetime.strptime(field("date_of_birth"), "%Y-%m-%d").date()
        if date_of_birth > date.today():
            errors.append(f"row {number}: date_of_birth {date_of_birth} is in the future")
    except ValueError:
        errors.append(
            f"row {number}: date_of_birth {field('date_of_birth')!r} is not ISO YYYY-MM-DD"
        )

    # A blank cell means the question was never asked -> NULL. It is NOT
    # prefer_not_to_say, which means the gymnast was asked and declined.
    ethnicity = None
    if field("ethnicity"):
        try:
            ethnicity = Ethnicity(field("ethnicity"))
        except ValueError:
            errors.append(
                f"row {number}: ethnicity {field('ethnicity')!r} is not a valid Ethnicity"
            )

    level = None
    try:
        level = Level(field("level"))
    except ValueError:
        errors.append(f"row {number}: level {field('level')!r} is not a valid Level")

    age_group = None
    try:
        age_group = AgeGroup(field("age_group"))
    except ValueError:
        errors.append(f"row {number}: age_group {field('age_group')!r} is not a valid AgeGroup")

    district_name = field("district_name")
    club_name = field("club_name")
    if district_name not in DISTRICT_ABBREVIATIONS:
        errors.append(
            f"row {number}: unknown district {district_name!r}\n"
            f"  Add to DISTRICT_ABBREVIATIONS in scripts/import_roster.py:\n"
            f'      "{district_name}": "ABBREV",'
        )
    if (district_name, club_name) not in CLUB_ABBREVIATIONS:
        errors.append(
            f"row {number}: unknown club {club_name!r} (district {district_name!r})\n"
            f"  Add to CLUB_ABBREVIATIONS in scripts/import_roster.py:\n"
            f'      ("{district_name}", "{club_name}"): "ABBREV",'
        )

    # Without these three there is no row to build. Everything else is still reported.
    if date_of_birth is None or level is None or age_group is None:
        return None

    return RosterRow(
        row_number=number,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
        gsa_number=field("gsa_number") or None,
        ethnicity=ethnicity,
        district_name=district_name,
        club_name=club_name,
        level=level,
        age_group=age_group,
    )


def parse_csv(path: Path | str) -> tuple[list[RosterRow], list[str]]:
    """
    Read and validate the CSV.

    Returns (rows, errors). Every problem across every row is collected rather than
    raising on the first, so one run tells you everything to fix.

    `rows` is only safe to use when `errors` is empty -- a row that fails name or
    ethnicity validation is still returned. main() aborts on any error, so partial rows
    never reach import_roster.
    """
    errors: list[str] = []
    rows: list[RosterRow] = []

    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            return [], [f"missing required column(s): {', '.join(missing)}"]

        # start=2 because the header occupies line 1, so numbers match what a
        # spreadsheet shows.
        for number, raw in enumerate(reader, start=2):
            row = _parse_row(number, raw, errors)
            if row is not None:
                rows.append(row)

    return rows, errors
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
pytest test/test_scripts/test_import_roster.py -v
```

Expected: 8 passed.

- [ ] **Step 6: Verify against the real CSV**

```bash
python -c "
from scripts.import_roster import parse_csv
rows, errors = parse_csv('../bulkupload/rhythmiq_import_participants.csv')
print('rows', len(rows), 'errors', len(errors))
print('distinct gymnasts', len({r.match_key for r in rows}))
"
```

Expected exactly:
```
rows 93 errors 0
distinct gymnasts 90
```

If the distinct count is not 90, `match_key` is wrong — stop and fix it before continuing.

- [ ] **Step 7: Lint and commit**

```bash
ruff check . && ruff format .
git add scripts/import_roster.py test/test_scripts/
git commit -m "feat: parse and validate roster import CSV"
```

---

### Task 2: Cross-row consistency checks

**Files:**
- Modify: `backend/scripts/import_roster.py` (append after `parse_csv`)
- Modify: `backend/test/test_scripts/test_import_roster.py`

**Interfaces:**
- Consumes: `RosterRow` and its `identity` property from Task 1.
- Produces: `check_consistency(rows: list[RosterRow]) -> list[str]`

- [ ] **Step 1: Write the failing tests**

Add to the import line in `test_import_roster.py` so it reads:

```python
from scripts.import_roster import RosterRow, check_consistency, parse_csv
```

Append these tests:

```python
def test_clean_rows_pass_consistency():
    rows = [
        make_row(row_number=2, first_name="Anna", gsa_number="1"),
        make_row(row_number=3, first_name="Bella", gsa_number="2"),
    ]

    assert check_consistency(rows) == []


def test_duplicate_rows_for_the_same_gymnast_are_consistent():
    # The real file does this: one gymnast entered in two single-apparatus events.
    rows = [make_row(row_number=2), make_row(row_number=3)]

    assert check_consistency(rows) == []


def test_club_under_two_districts_is_rejected():
    rows = [
        make_row(row_number=2, gsa_number="1", district_name="Eden", club_name="Zest"),
        make_row(
            row_number=3,
            first_name="Bella",
            gsa_number="2",
            district_name="Cape Winelands",
            club_name="Zest",
        ),
    ]

    errors = check_consistency(rows)

    assert len(errors) == 1
    assert "club 'Zest' appears under multiple districts" in errors[0]


def test_one_gsa_number_with_two_identities_is_rejected():
    rows = [
        make_row(row_number=2, first_name="Anna", gsa_number="1"),
        make_row(row_number=3, first_name="Bella", gsa_number="1"),
    ]

    errors = check_consistency(rows)

    assert len(errors) == 1
    assert "gsa_number '1' is used by more than one gymnast" in errors[0]


def test_one_identity_with_two_gsa_numbers_is_rejected():
    rows = [
        make_row(row_number=2, gsa_number="1"),
        make_row(row_number=3, gsa_number="2"),
    ]

    errors = check_consistency(rows)

    assert len(errors) == 1
    assert "has more than one gsa_number" in errors[0]
    assert "Anna Petrov" in errors[0]
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
pytest test/test_scripts/test_import_roster.py -v
```

Expected: collection error — `ImportError: cannot import name 'check_consistency'`.

- [ ] **Step 3: Write the implementation**

Append to `backend/scripts/import_roster.py`, after `parse_csv`:

```python
def check_consistency(rows: list[RosterRow]) -> list[str]:
    """
    Cross-row rules that no single row can reveal.

    Each of these would otherwise surface mid-insert as a confusing IntegrityError, or
    worse, quietly attach gymnasts to the wrong club.
    """
    errors: list[str] = []
    districts_by_club: dict[str, set[str]] = {}
    identities_by_gsa: dict[str, set[tuple[str, str, date]]] = {}
    gsas_by_identity: dict[tuple[str, str, date], set[str | None]] = {}

    for row in rows:
        districts_by_club.setdefault(row.club_name, set()).add(row.district_name)
        if row.gsa_number:
            identities_by_gsa.setdefault(row.gsa_number, set()).add(row.identity)
        gsas_by_identity.setdefault(row.identity, set()).add(row.gsa_number)

    for club_name, district_names in sorted(districts_by_club.items()):
        if len(district_names) > 1:
            errors.append(
                f"club {club_name!r} appears under multiple districts: "
                f"{sorted(district_names)}"
            )

    for gsa_number, identities in sorted(identities_by_gsa.items()):
        if len(identities) > 1:
            names = sorted(f"{first} {last} ({dob})" for first, last, dob in identities)
            errors.append(f"gsa_number {gsa_number!r} is used by more than one gymnast: {names}")

    for identity, gsa_numbers in sorted(gsas_by_identity.items()):
        if len(gsa_numbers) > 1:
            first, last, dob = identity
            listed = sorted(g or "(blank)" for g in gsa_numbers)
            errors.append(f"gymnast {first} {last} ({dob}) has more than one gsa_number: {listed}")

    return errors
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
pytest test/test_scripts/test_import_roster.py -v
```

Expected: 13 passed.

- [ ] **Step 5: Verify the real CSV is consistent**

```bash
python -c "
from scripts.import_roster import check_consistency, parse_csv
rows, _ = parse_csv('../bulkupload/rhythmiq_import_participants.csv')
print('consistency errors:', check_consistency(rows))
"
```

Expected exactly: `consistency errors: []`

- [ ] **Step 6: Lint and commit**

```bash
ruff check . && ruff format .
git add scripts/import_roster.py test/test_scripts/test_import_roster.py
git commit -m "feat: cross-row consistency checks for roster import"
```

---

### Task 3: Database import

**Files:**
- Modify: `backend/scripts/import_roster.py` (append after `check_consistency`)
- Modify: `backend/test/test_scripts/test_import_roster.py`

**Interfaces:**
- Consumes: `RosterRow` (`identity`, `match_key`), `DISTRICT_ABBREVIATIONS`, `CLUB_ABBREVIATIONS` from Task 1.
- Produces:
  - `ImportReport` — dataclass with list fields `districts_created`, `districts_existing`, `clubs_created`, `clubs_existing`, `gymnasts_created`, `gymnasts_existing`, `differences` (all `list[str]`)
  - `import_roster(rows: list[RosterRow], session: Session) -> ImportReport` — flushes, **never commits**

- [ ] **Step 1: Write the failing tests**

Update the imports at the top of `test_import_roster.py` so they read:

```python
from datetime import date
from pathlib import Path

from app.models import AgeGroup, Club, District, Ethnicity, Gymnast, Level
from scripts.import_roster import RosterRow, check_consistency, import_roster, parse_csv
from test.conftest import make_club, make_district
```

Append these tests:

```python
def test_cold_start_creates_district_club_and_gymnast(db_session):
    report = import_roster([make_row()], db_session)

    assert report.districts_created == ["Eden"]
    assert report.clubs_created == ["Zest (Eden)"]
    assert len(report.gymnasts_created) == 1
    assert report.differences == []

    district = db_session.query(District).filter_by(name="Eden").one()
    assert district.abbreviation == "EDEN"
    club = db_session.query(Club).filter_by(name="Zest").one()
    assert club.abbreviation == "ZEST"
    assert club.district_id == district.id
    gymnast = db_session.query(Gymnast).filter_by(gsa_number="10001").one()
    assert gymnast.first_name == "Anna"
    assert gymnast.club_id == club.id
    assert gymnast.country_code is None


def test_rerunning_the_same_rows_is_a_no_op(db_session):
    rows = [make_row()]
    import_roster(rows, db_session)

    report = import_roster(rows, db_session)

    assert report.districts_created == []
    assert report.clubs_created == []
    assert report.gymnasts_created == []
    assert len(report.gymnasts_existing) == 1
    assert report.differences == []
    assert db_session.query(Gymnast).count() == 1
    assert db_session.query(Club).count() == 1
    assert db_session.query(District).count() == 1


def test_duplicate_rows_for_one_gymnast_create_a_single_row(db_session):
    # Mirrors the real file's three two-row gymnasts.
    report = import_roster([make_row(row_number=2), make_row(row_number=3)], db_session)

    assert len(report.gymnasts_created) == 1
    assert db_session.query(Gymnast).count() == 1


def test_gsa_number_matches_a_gymnast_whose_name_changed(db_session):
    import_roster([make_row(first_name="Anné")], db_session)

    report = import_roster([make_row(first_name="Anne")], db_session)

    assert report.gymnasts_created == []
    assert len(report.gymnasts_existing) == 1
    assert any("first_name: Anné -> Anne" in d for d in report.differences)
    # Reported, not applied.
    assert db_session.query(Gymnast).one().first_name == "Anné"


def test_blank_gsa_number_falls_back_to_identity_matching(db_session):
    import_roster([make_row(gsa_number=None)], db_session)

    report = import_roster([make_row(gsa_number=None)], db_session)

    assert report.gymnasts_created == []
    assert len(report.gymnasts_existing) == 1
    assert db_session.query(Gymnast).count() == 1


def test_a_changed_club_is_reported_but_not_applied(db_session):
    district = make_district(db_session, name="Eden", abbreviation="EDEN")
    old_club = make_club(db_session, district=district, name="Old Club", abbreviation="OLD")
    db_session.add(
        Gymnast(
            first_name="Anna",
            last_name="Petrov",
            date_of_birth=date(2016, 10, 1),
            gsa_number="10001",
            club_id=old_club.id,
        )
    )
    db_session.flush()

    report = import_roster([make_row()], db_session)

    assert report.gymnasts_created == []
    assert any("club: Old Club -> Zest" in d for d in report.differences)
    gymnast = db_session.query(Gymnast).filter_by(gsa_number="10001").one()
    assert gymnast.club_id == old_club.id  # unchanged


def test_a_newly_recorded_ethnicity_is_reported_but_not_applied(db_session):
    import_roster([make_row(ethnicity=None)], db_session)

    report = import_roster([make_row(ethnicity=Ethnicity.white)], db_session)

    assert any("ethnicity: NULL -> white" in d for d in report.differences)
    assert db_session.query(Gymnast).one().ethnicity is None


def test_blank_ethnicity_is_stored_as_null(db_session):
    import_roster([make_row(ethnicity=None)], db_session)

    gymnast = db_session.query(Gymnast).one()
    assert gymnast.ethnicity is None
    assert gymnast.ethnicity is not Ethnicity.prefer_not_to_say


def test_import_does_not_commit(db_session):
    import_roster([make_row()], db_session)

    # The fixture binds the Session to a connection that already has a transaction open,
    # so SQLAlchemy runs the Session on a SAVEPOINT. A rollback here therefore undoes
    # only what import_roster did, leaving the fixture's outer transaction healthy. Had
    # import_roster committed, the savepoint would already be released and the row would
    # survive this rollback.
    db_session.rollback()
    assert db_session.query(Gymnast).count() == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
pytest test/test_scripts/test_import_roster.py -v
```

Expected: collection error — `ImportError: cannot import name 'import_roster'`.

- [ ] **Step 3: Write the implementation**

Add `field` to the dataclasses import at the top of the file so it reads:

```python
from dataclasses import dataclass, field
```

Add these imports below it:

```python
from sqlalchemy.orm import Session

from app.models import AgeGroup, Club, District, Ethnicity, Gymnast, Level
```

(replacing the existing `from app.models import AgeGroup, Ethnicity, Level` line).

Append after `check_consistency`:

```python
@dataclass
class ImportReport:
    """What a run did, or in a dry run, would do."""

    districts_created: list[str] = field(default_factory=list)
    districts_existing: list[str] = field(default_factory=list)
    clubs_created: list[str] = field(default_factory=list)
    clubs_existing: list[str] = field(default_factory=list)
    gymnasts_created: list[str] = field(default_factory=list)
    gymnasts_existing: list[str] = field(default_factory=list)
    differences: list[str] = field(default_factory=list)


def _resolve_districts(
    rows: list[RosterRow], session: Session, report: ImportReport
) -> dict[str, District]:
    districts: dict[str, District] = {}
    for name in sorted({row.district_name for row in rows}):
        district = session.query(District).filter(District.name == name).first()
        if district is None:
            district = District(name=name, abbreviation=DISTRICT_ABBREVIATIONS[name])
            session.add(district)
            session.flush()  # populate district.id for the clubs below
            report.districts_created.append(name)
        else:
            report.districts_existing.append(name)
            expected = DISTRICT_ABBREVIATIONS[name]
            if district.abbreviation != expected:
                report.differences.append(
                    f"  district {name}  abbreviation: {district.abbreviation} -> {expected}"
                )
        districts[name] = district
    return districts


def _resolve_clubs(
    rows: list[RosterRow],
    session: Session,
    districts: dict[str, District],
    report: ImportReport,
) -> dict[tuple[str, str], Club]:
    clubs: dict[tuple[str, str], Club] = {}
    for district_name, club_name in sorted({(r.district_name, r.club_name) for r in rows}):
        district = districts[district_name]
        label = f"{club_name} ({district_name})"
        club = (
            session.query(Club)
            .filter(Club.district_id == district.id, Club.name == club_name)
            .first()
        )
        if club is None:
            club = Club(
                district_id=district.id,
                name=club_name,
                abbreviation=CLUB_ABBREVIATIONS[(district_name, club_name)],
            )
            session.add(club)
            session.flush()  # populate club.id for the gymnasts below
            report.clubs_created.append(label)
        else:
            report.clubs_existing.append(label)
            expected = CLUB_ABBREVIATIONS[(district_name, club_name)]
            if club.abbreviation != expected:
                report.differences.append(
                    f"  club {label}  abbreviation: {club.abbreviation} -> {expected}"
                )
        clubs[(district_name, club_name)] = club
    return clubs


def _find_gymnast(session: Session, row: RosterRow) -> Gymnast | None:
    """
    GSA number first, identity second.

    Gymnast carries two competing unique keys -- uq_gymnast_gsa_number and
    uq_gymnast_identity on (first_name, last_name, date_of_birth) -- and they disagree
    the moment a name spelling or DOB is corrected in the CSV. Matching on identity
    first would find nothing, attempt an insert, and collide on the GSA constraint
    mid-run. The GSA number is the real membership ID, so it is the stabler key.
    """
    if row.gsa_number:
        existing = session.query(Gymnast).filter(Gymnast.gsa_number == row.gsa_number).first()
        if existing is not None:
            return existing
    return (
        session.query(Gymnast)
        .filter(
            Gymnast.first_name == row.first_name,
            Gymnast.last_name == row.last_name,
            Gymnast.date_of_birth == row.date_of_birth,
        )
        .first()
    )


def _show(value: object) -> str:
    return "NULL" if value is None else str(value)


def _gymnast_differences(
    gymnast: Gymnast, row: RosterRow, club: Club, session: Session
) -> list[str]:
    label = f"{row.first_name} {row.last_name}"
    if row.gsa_number:
        label += f" (GSA {row.gsa_number})"

    stored_club = session.get(Club, gymnast.club_id) if gymnast.club_id else None
    candidates = (
        ("first_name", gymnast.first_name, row.first_name),
        ("last_name", gymnast.last_name, row.last_name),
        ("date_of_birth", gymnast.date_of_birth, row.date_of_birth),
        ("gsa_number", gymnast.gsa_number, row.gsa_number),
        ("ethnicity", gymnast.ethnicity, row.ethnicity),
        ("club", stored_club.name if stored_club else None, club.name),
    )
    return [
        f"  {label}  {name}: {_show(stored)} -> {_show(incoming)}"
        for name, stored, incoming in candidates
        if stored != incoming
    ]


def _resolve_gymnasts(
    rows: list[RosterRow],
    session: Session,
    clubs: dict[tuple[str, str], Club],
    report: ImportReport,
) -> None:
    # One gymnast may occupy several rows (one per single-apparatus event), so collapse
    # to the first row per match_key before touching the database.
    unique_rows: dict[tuple[str, object], RosterRow] = {}
    for row in rows:
        unique_rows.setdefault(row.match_key, row)

    for row in unique_rows.values():
        club = clubs[(row.district_name, row.club_name)]
        label = f"{row.first_name} {row.last_name}"
        gymnast = _find_gymnast(session, row)
        if gymnast is None:
            session.add(
                Gymnast(
                    first_name=row.first_name,
                    last_name=row.last_name,
                    date_of_birth=row.date_of_birth,
                    gsa_number=row.gsa_number,
                    ethnicity=row.ethnicity,
                    club_id=club.id,
                )
            )
            session.flush()
            report.gymnasts_created.append(label)
        else:
            report.gymnasts_existing.append(label)
            # Existing gymnasts are never modified: a stale or wrong CSV must not be able
            # to damage hand-corrected data. Differences are reported for you to act on.
            report.differences.extend(_gymnast_differences(gymnast, row, club, session))


def import_roster(rows: list[RosterRow], session: Session) -> ImportReport:
    """
    Create missing districts, clubs and gymnasts; report differences on existing ones.

    Flushes but deliberately never commits -- the caller decides, which is what makes
    the dry run a real transaction that gets rolled back rather than a simulation.
    """
    report = ImportReport()
    districts = _resolve_districts(rows, session, report)
    clubs = _resolve_clubs(rows, session, districts, report)
    _resolve_gymnasts(rows, session, clubs, report)
    session.flush()
    return report
```

- [ ] **Step 4: Run the tests to verify they pass**

Postgres must be up — from the repo root, `make dev` first if needed.

```bash
pytest test/test_scripts/test_import_roster.py -v
```

Expected: 22 passed.

- [ ] **Step 5: Run the whole suite for regressions**

```bash
pytest
```

Expected: all tests pass. Nothing outside `scripts/` and `test/test_scripts/` changed, so any failure here is a real problem — investigate rather than proceeding.

- [ ] **Step 6: Lint and commit**

```bash
ruff check . && ruff format .
git add scripts/import_roster.py test/test_scripts/test_import_roster.py
git commit -m "feat: import roster rows into districts, clubs and gymnasts"
```

---

### Task 4: CLI, report formatting and docs

**Files:**
- Modify: `backend/scripts/import_roster.py` (append after `import_roster`)
- Modify: `backend/test/test_scripts/test_import_roster.py`
- Modify: `CLAUDE.md` (repo root)

**Interfaces:**
- Consumes: `ImportReport`, `import_roster`, `parse_csv`, `check_consistency` from Tasks 1–3.
- Produces: `format_report(report: ImportReport, *, committed: bool) -> str`, `main() -> int`

- [ ] **Step 1: Write the failing tests**

Update the script import line in `test_import_roster.py` so it reads:

```python
from scripts.import_roster import (
    RosterRow,
    check_consistency,
    format_report,
    import_roster,
    parse_csv,
)
```

Append:

```python
def test_report_counts_creations_and_marks_a_dry_run(db_session):
    report = import_roster([make_row()], db_session)

    text = format_report(report, committed=False)

    # Exact spacing: label is left-padded to 11, total right-aligned in 3.
    assert "Districts:   1 (1 created, 0 existing)" in text
    assert "Clubs:       1 (1 created, 0 existing)" in text
    assert "Gymnasts:    1 (1 created, 0 existing)" in text
    assert "DRY RUN" in text
    assert "--commit" in text


def test_report_marks_a_committed_run(db_session):
    report = import_roster([make_row()], db_session)

    text = format_report(report, committed=True)

    assert "DRY RUN" not in text
    assert "Committed." in text


def test_report_lists_differences_and_says_nothing_changed(db_session):
    import_roster([make_row(ethnicity=None)], db_session)
    report = import_roster([make_row(ethnicity=Ethnicity.white)], db_session)

    text = format_report(report, committed=False)

    assert "1 existing gymnast differs from the CSV (nothing changed):" in text
    assert "ethnicity: NULL -> white" in text


def test_report_omits_the_difference_section_when_there_are_none(db_session):
    report = import_roster([make_row()], db_session)

    assert "differs from the CSV" not in format_report(report, committed=False)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
pytest test/test_scripts/test_import_roster.py -v
```

Expected: collection error — `ImportError: cannot import name 'format_report'`.

- [ ] **Step 3: Write the implementation**

Add these imports at the top of `backend/scripts/import_roster.py`:

```python
import argparse

from app.db import SessionLocal
```

Append after `import_roster`:

```python
def format_report(report: ImportReport, *, committed: bool) -> str:
    def line(label: str, created: list[str], existing: list[str]) -> str:
        total = len(created) + len(existing)
        return f"{label:<11}{total:>3} ({len(created)} created, {len(existing)} existing)"

    lines = [
        line("Districts:", report.districts_created, report.districts_existing),
        line("Clubs:", report.clubs_created, report.clubs_existing),
        line("Gymnasts:", report.gymnasts_created, report.gymnasts_existing),
    ]

    if report.differences:
        count = len(report.gymnasts_existing)
        noun = "gymnast differs" if count == 1 else "gymnasts differ"
        lines.append("")
        lines.append(f"{count} existing {noun} from the CSV (nothing changed):")
        lines.extend(report.differences)

    lines.append("")
    if committed:
        lines.append("Committed.")
    else:
        lines.append("DRY RUN -- nothing written. Re-run with --commit to apply.")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("csv_path", type=Path, help="Path to the participant roster CSV")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Write to the database. Without it the run is a dry run and is rolled back.",
    )
    args = parser.parse_args()

    rows, errors = parse_csv(args.csv_path)
    # Only worth checking cross-row rules once every row parses -- consistency errors
    # derived from half-read rows are noise on top of the real problem.
    if not errors:
        errors = check_consistency(rows)
    if errors:
        print(f"{len(errors)} problem(s) found -- nothing written:\n")
        for error in errors:
            print(f"  {error}")
        return 1

    session = SessionLocal()
    try:
        report = import_roster(rows, session)
        print(format_report(report, committed=args.commit))
        if args.commit:
            session.commit()
        else:
            session.rollback()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
pytest test/test_scripts/test_import_roster.py -v
```

Expected: 26 passed.

- [ ] **Step 5: Dry-run against the real CSV**

```bash
python -m scripts.import_roster ../bulkupload/rhythmiq_import_participants.csv
```

Expected output (assuming a database with none of this data yet):

```
Districts:   3 (3 created, 0 existing)
Clubs:       6 (6 created, 0 existing)
Gymnasts:   90 (90 created, 0 existing)

DRY RUN -- nothing written. Re-run with --commit to apply.
```

The counts **must** be 3 / 6 / 90. Then confirm the dry run wrote nothing:

```bash
python -c "
from app.db import SessionLocal
from app.models import Gymnast
session = SessionLocal()
print('gymnasts in db:', session.query(Gymnast).count())
session.close()
"
```

Expected: unchanged from before the dry run.

Do **not** run `--commit` — leave that decision to the user.

- [ ] **Step 6: Document the script in CLAUDE.md**

In `CLAUDE.md`, under **Architecture**, immediately after the `scripts/seed_demo_data.py` bullet, add:

```markdown
- `scripts/import_roster.py` — imports a participant CSV (`bulkupload/`) into districts,
  clubs and gymnasts. Dry run by default; `--commit` writes. Matches existing gymnasts on
  `gsa_number` first and `(first_name, last_name, date_of_birth)` second, and *reports*
  differences rather than applying them. District/club abbreviations are hardcoded tables
  keyed by name and by `(district, club)` — an unknown name aborts the run with the line
  to add. Meet entries and routines are deliberately out of scope (see
  `docs/superpowers/specs/2026-07-21-roster-csv-import-design.md`).
```

- [ ] **Step 7: Run the whole suite, lint and commit**

```bash
pytest
ruff check . && ruff format .
git add scripts/import_roster.py test/test_scripts/test_import_roster.py ../CLAUDE.md
git commit -m "feat: roster import CLI with dry-run default and difference report"
```

---

## Verification checklist

Before declaring the work done, confirm each of these by running it:

- [ ] `cd backend && pytest` — full suite passes
- [ ] `ruff check .` — clean
- [ ] `python -m scripts.import_roster ../bulkupload/rhythmiq_import_participants.csv` prints 3 districts / 6 clubs / 90 gymnasts and `DRY RUN`
- [ ] The gymnast count in the database is unchanged after that dry run
- [ ] `git log --oneline` shows four `feat:` commits
- [ ] `bulkupload/rhythmiq_import_participants.csv` is unmodified (`git status` clean)
