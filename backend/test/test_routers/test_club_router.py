"""
Test suite for the club router.
- A club belongs to a district (district_id), pre-checked for existence on create.
- name/abbreviation are unique per district, but the same values are allowed across
  different districts.
- DELETE is rejected (409) while the club still has gymnasts or coaches (RESTRICT FKs).
"""

import pytest

from app.models import Club
from test.conftest import make_club, make_coach, make_district, make_gymnast


##-- POST /clubs --##
def test_create_club_happy_path(client, db_session):
    district = make_district(db_session, name="Western Province", abbreviation="WP")

    response = client.post(
        "/clubs",
        json={"name": "Western Province Warriors", "district_id": district.id, "abbreviation": "WPW"},
    )

    assert response.status_code == 201
    body = response.json()
    assert isinstance(body.pop("id"), int)
    assert body == {
        "name": "Western Province Warriors",
        "district_id": district.id,
        "abbreviation": "WPW",
    }


def test_create_club_strips_whitespace(client, db_session):
    district = make_district(db_session)

    response = client.post(
        "/clubs",
        json={"name": "  Southern Stars  ", "district_id": district.id, "abbreviation": "  SS  "},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Southern Stars"
    assert body["abbreviation"] == "SS"


@pytest.mark.parametrize(
    "payload",
    [
        {"district_id": 1, "abbreviation": "NS"},
        {"name": "Northern Stars", "abbreviation": "NS"},
        {"name": "Northern Stars", "district_id": 1},
        {"name": "N", "district_id": 1, "abbreviation": "NS"},
        {"name": "Northern Stars", "district_id": 0, "abbreviation": "NS"},
        {"name": "Northern Stars", "district_id": -1, "abbreviation": "NS"},
        {"name": "Northern Stars", "district_id": 1, "abbreviation": ""},
    ],
)
def test_create_club_rejects_invalid_payloads(client, payload):
    # There's no districts in the test DB, so any district_id will be invalid. The point of this test is to
    # ensure that the request is rejected due to validation errors, not because of a missing district.
    response = client.post("/clubs", json=payload)

    assert response.status_code == 422


def test_create_club_returns_404_for_missing_district(client):
    response = client.post(
        "/clubs",
        json={"name": "Northern Stars", "district_id": 999, "abbreviation": "NS"},
    )

    assert response.status_code == 404


def test_create_club_rejects_duplicate_name_within_district(client, db_session):
    district = make_district(db_session, name="Western Province", abbreviation="WP")
    make_club(db_session, district=district, name="Van Der Stel", abbreviation="VDS")

    response = client.post(
        "/clubs",
        json={"name": "Van Der Stel", "district_id": district.id, "abbreviation": "VDS2"},
    )

    assert response.status_code == 409


def test_create_club_rejects_duplicate_abbreviation_within_district(client, db_session):
    district = make_district(db_session, name="Capital District", abbreviation="CAP")
    make_club(db_session, district=district, name="Capital Stars", abbreviation="CS")

    response = client.post(
        "/clubs",
        json={"name": "Capital Queens", "district_id": district.id, "abbreviation": "CS"},
    )

    assert response.status_code == 409


def test_create_club_allows_same_values_in_different_districts(client, db_session):
    district_one = make_district(db_session, name="District One", abbreviation="D1")
    district_two = make_district(db_session, name="District Two", abbreviation="D2")

    first = client.post(
        "/clubs",
        json={"name": "Shared Club", "district_id": district_one.id, "abbreviation": "SC"},
    )
    second = client.post(
        "/clubs",
        json={"name": "Shared Club", "district_id": district_two.id, "abbreviation": "SC"},
    )

    assert first.status_code == 201
    assert second.status_code == 201

## -- GET /clubs and GET /clubs/{id} --#
def test_list_clubs_returns_all_clubs(client, db_session):
    district = make_district(db_session, name="List District", abbreviation="LD")
    first_club = make_club(db_session, district=district, name="List One", abbreviation="L1")
    second_club = make_club(db_session, district=district, name="List Two", abbreviation="L2")

    response = client.get("/clubs")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": first_club.id,
            "name": first_club.name,
            "district_id": district.id,
            "abbreviation": first_club.abbreviation,
        },
        {
            "id": second_club.id,
            "name": second_club.name,
            "district_id": district.id,
            "abbreviation": second_club.abbreviation,
        },
    ]


def test_get_club_returns_one_club(client, db_session):
    district = make_district(db_session, name="Read District", abbreviation="RD")
    club = make_club(db_session, district=district, name="Read Club", abbreviation="RC")

    response = client.get(f"/clubs/{club.id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": club.id,
        "name": club.name,
        "district_id": district.id,
        "abbreviation": club.abbreviation,
    }


def test_get_club_returns_404_for_missing_club(client):
    response = client.get("/clubs/999")

    assert response.status_code == 404

##-- PATCH /clubs/{id} --##
def test_update_club_partial_fields(client, db_session):
    district = make_district(db_session, name="Update District", abbreviation="UD")
    club = make_club(db_session, district=district, name="Update Club", abbreviation="UC")

    response = client.patch(f"/clubs/{club.id}", json={"name": "Updated Club"})

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Club"
    assert response.json()["abbreviation"] == "UC"

def test_update_abbreviation_of_club(client, db_session):
    district = make_district(db_session, name="Update Abbreviation District", abbreviation="UAD")
    club = make_club(db_session, district=district, name="Update Abbreviation Club", abbreviation="UAC")

    response = client.patch(f"/clubs/{club.id}", json={"abbreviation": "UAC2"})

    assert response.status_code == 200
    assert response.json()["name"] == "Update Abbreviation Club"
    assert response.json()["abbreviation"] == "UAC2"

def test_update_club_strips_whitespace(client, db_session):
    district = make_district(db_session, name="Trim District", abbreviation="TD")
    club = make_club(db_session, district=district, name="Trim Club", abbreviation="TC")

    response = client.patch(
        f"/clubs/{club.id}",
        json={"name": "  Trimmed Club  ", "abbreviation": "  TC2  "},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Trimmed Club"
    assert response.json()["abbreviation"] == "TC2"


def test_update_club_rejects_duplicate_name(client, db_session):
    district = make_district(db_session, name="Dup District", abbreviation="DD")
    club = make_club(db_session, district=district, name="Original Club", abbreviation="OC")
    make_club(db_session, district=district, name="Taken Club", abbreviation="TC")

    response = client.patch(f"/clubs/{club.id}", json={"name": "Taken Club"})

    assert response.status_code == 409

def test_update_club_not_found(client):
    response = client.patch("/clubs/999", json={"name": "Ghost"})

    assert response.status_code == 404

def test_update_body_empty(client, db_session):
    district = make_district(db_session, name="Empty District", abbreviation="ED")
    club = make_club(db_session, district=district, name="Empty Club", abbreviation="EC")

    # The router has exclude_unset=True, so sending an empty body is a valid no-op. It should return 200 and not change anything.
    response = client.patch(f"/clubs/{club.id}", json={})

    assert response.status_code == 200

##-- DELETE /clubs/{id} --##
def test_delete_club_success(client, db_session):
    district = make_district(db_session, name="Delete District", abbreviation="DEL")
    club = make_club(db_session, district=district, name="Delete Club", abbreviation="DC")

    response = client.delete(f"/clubs/{club.id}")

    assert response.status_code == 204
    # DB confirms it's gone
    assert db_session.query(Club).filter_by(id=club.id).first() is None
    #expect 404 when trying to get the deleted club
    get_response = client.get(f"/clubs/{club.id}")
    assert get_response.status_code == 404


def test_delete_club_returns_404_for_missing_club(client):
    response = client.delete("/clubs/999")

    assert response.status_code == 404


def test_delete_club_with_gymnasts_returns_conflict(client, db_session):
    # FK constraint will prevent deletion of a club that has gymnasts associated with it
    club = make_club(db_session)
    make_gymnast(db_session, club=club)

    response = client.delete(f"/clubs/{club.id}")

    assert response.status_code == 409


def test_delete_club_with_coaches_returns_conflict(client, db_session):
    # FK constraint will prevent deletion of a club that has coaches associated with it
    club = make_club(db_session, name="Coach Blocked Club", abbreviation="CBC")
    make_coach(db_session, club=club)

    response = client.delete(f"/clubs/{club.id}")

    assert response.status_code == 409
