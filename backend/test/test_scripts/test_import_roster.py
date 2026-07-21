"""
Tests for scripts/import_roster.py.

Split to mirror the script's own phases: parsing/validation and cross-row consistency
are pure and need no database; import_roster gets the db_session fixture.
"""

from datetime import date
from pathlib import Path

from app.models import AgeGroup, Ethnicity, Level
from scripts.import_roster import RosterRow, check_consistency, parse_csv

FIXTURES = Path(__file__).parent / "fixtures"


def make_row(**overrides) -> RosterRow:
    """A valid RosterRow, so each test only states the field it cares about."""
    defaults = {
        "row_number": 2,
        "first_name": "Anna",
        "last_name": "Petrov",
        "date_of_birth": date(2016, 10, 1),
        "gsa_number": "10001",
        "ethnicity": Ethnicity.white,
        "district_name": "Eden",
        "club_name": "Zest",
        "level": Level.level_1,
        "age_group": AgeGroup.under_9,
    }
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
