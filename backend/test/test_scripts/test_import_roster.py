"""
Tests for scripts/import_roster.py.

Split to mirror the script's own phases: parsing/validation and cross-row consistency
are pure and need no database; import_roster gets the db_session fixture.
"""

from datetime import date
from pathlib import Path

from app.models import AgeGroup, Club, District, Ethnicity, Gymnast, Level
from scripts.import_roster import (
    RosterRow,
    check_consistency,
    format_report,
    import_roster,
    parse_csv,
)
from test.conftest import make_club, make_district

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


def test_a_move_between_same_named_clubs_in_different_districts_is_reported(db_session):
    # uq_club_name is scoped by district_id, so two districts may each have a "Zest".
    # A name-only comparison would see "Zest" == "Zest" and report no change at all.
    other_district = make_district(db_session, name="Cape Winelands", abbreviation="CWDM")
    other_zest = make_club(db_session, district=other_district, name="Zest", abbreviation="ZST2")
    db_session.add(
        Gymnast(
            first_name="Anna",
            last_name="Petrov",
            date_of_birth=date(2016, 10, 1),
            gsa_number="10001",
            club_id=other_zest.id,
        )
    )
    db_session.flush()

    # make_row() defaults to district Eden / club Zest -- a *different* Zest.
    report = import_roster([make_row()], db_session)

    assert report.gymnasts_created == []
    club_diffs = [d for d in report.differences if "club:" in d]
    assert len(club_diffs) == 1
    assert "Zest (Cape Winelands) -> Zest (Eden)" in club_diffs[0]
    gymnast = db_session.query(Gymnast).filter_by(gsa_number="10001").one()
    assert gymnast.club_id == other_zest.id  # unchanged


def test_a_district_abbreviation_mismatch_is_reported(db_session):
    make_district(db_session, name="Eden", abbreviation="EDN")  # table says EDEN

    report = import_roster([make_row()], db_session)

    assert any("district Eden  abbreviation: EDN -> EDEN" in d for d in report.differences)
    district = db_session.query(District).filter_by(name="Eden").one()
    assert district.abbreviation == "EDN"  # unchanged


def test_a_club_abbreviation_mismatch_is_reported(db_session):
    district = make_district(db_session, name="Eden", abbreviation="EDEN")
    make_club(db_session, district=district, name="Zest", abbreviation="ZST")  # table says ZEST

    report = import_roster([make_row()], db_session)

    assert any("club Zest (Eden)  abbreviation: ZST -> ZEST" in d for d in report.differences)
    club = db_session.query(Club).filter_by(name="Zest").one()
    assert club.abbreviation == "ZST"  # unchanged


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

    assert "1 difference found (nothing changed):" in text
    assert "ethnicity: NULL -> white" in text


def test_report_omits_the_difference_section_when_there_are_none(db_session):
    report = import_roster([make_row()], db_session)

    assert "nothing changed" not in format_report(report, committed=False)


def test_difference_count_follows_difference_lines_not_matched_gymnasts(db_session):
    # Two distinct gymnasts match on re-import (both land in gymnasts_existing), but only
    # one of them actually differs. The header must count the difference below, not the
    # two matched gymnasts -- this is exactly what len(report.gymnasts_existing) gets wrong.
    row_a = make_row(
        gsa_number="10001",
        first_name="Anna",
        last_name="Petrov",
        date_of_birth=date(2016, 10, 1),
        ethnicity=Ethnicity.white,
    )
    row_b = make_row(
        gsa_number="10002",
        first_name="Boipelo",
        last_name="Khumalo",
        date_of_birth=date(2015, 5, 5),
        ethnicity=Ethnicity.black,
    )
    import_roster([row_a, row_b], db_session)
    row_b_changed = make_row(
        gsa_number="10002",
        first_name="Boipelo",
        last_name="Khumalo",
        date_of_birth=date(2015, 5, 5),
        ethnicity=None,
    )

    report = import_roster([row_a, row_b_changed], db_session)

    assert len(report.gymnasts_existing) == 2
    text = format_report(report, committed=False)
    assert "1 difference found (nothing changed):" in text


def test_difference_count_uses_plural_wording_for_more_than_one(db_session):
    # A district abbreviation mismatch and a club abbreviation mismatch are both
    # non-gymnast differences -- two lines from a single row, proving the count is over
    # report.differences, not any per-entity list.
    district = make_district(db_session, name="Eden", abbreviation="EDN")  # table says EDEN
    make_club(db_session, district=district, name="Zest", abbreviation="ZST")  # table says ZEST

    report = import_roster([make_row()], db_session)

    assert len(report.differences) == 2
    text = format_report(report, committed=False)
    assert "2 differences found (nothing changed):" in text
