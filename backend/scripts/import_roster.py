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
                f"club {club_name!r} appears under multiple districts: {sorted(district_names)}"
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
