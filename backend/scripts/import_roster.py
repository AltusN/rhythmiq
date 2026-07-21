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
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import AgeGroup, Club, District, Ethnicity, Gymnast, Level

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

    candidates = (
        ("first_name", gymnast.first_name, row.first_name),
        ("last_name", gymnast.last_name, row.last_name),
        ("date_of_birth", gymnast.date_of_birth, row.date_of_birth),
        ("gsa_number", gymnast.gsa_number, row.gsa_number),
        ("ethnicity", gymnast.ethnicity, row.ethnicity),
    )
    differences = [
        f"  {label}  {name}: {_show(stored)} -> {_show(incoming)}"
        for name, stored, incoming in candidates
        if stored != incoming
    ]

    # Compared by id, never by name: uq_club_name is scoped by district_id, so two
    # districts may each have a club of the same name and a name comparison would
    # silently miss a move between them.
    if gymnast.club_id != club.id:
        stored_club = session.get(Club, gymnast.club_id) if gymnast.club_id else None
        stored_name = stored_club.name if stored_club else None
        incoming_name = club.name
        if stored_club is not None and stored_name == incoming_name:
            # Same name in two districts -- qualify both sides so the line does not
            # read as the nonsense "club: Zest -> Zest".
            stored_district = session.get(District, stored_club.district_id)
            stored_name = f"{stored_name} ({stored_district.name})"
            incoming_name = f"{incoming_name} ({row.district_name})"
        differences.append(f"  {label}  club: {_show(stored_name)} -> {incoming_name}")

    return differences


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
