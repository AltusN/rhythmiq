"""
    Test for the district router. Test POST / GET / PATCH / DELETE endpoints for districts.
"""
from test.conftest import make_club, make_district


##-- POST /districts --##
def test_create_district_success(client, db_session):
    response = client.post(
        "/districts",
        json={"name": "Eastern Cape", "abbreviation": "EC"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Eastern Cape"
    assert body["abbreviation"] == "EC"
    assert "id" in body

def test_district_create_with_whitespace_name(client, db_session):
    response = client.post(
        "/districts",
        json={"name": "  Western Cape  ", "abbreviation": "WC"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Western Cape"
    assert body["abbreviation"] == "WC"
    assert "id" in body

def test_create_district_duplicate_name(client, db_session):
    # Create the first district
    make_district(db_session, name="Northern Cape", abbreviation="NC")

    response = client.post(
        "/districts",
        json={"name": "Northern Cape2", "abbreviation": "NC"},
    )
    assert response.status_code == 409

def test_create_district_duplicate_abbreviation(client, db_session):
    # Create the first district
    make_district(db_session, name="Free State", abbreviation="FS")

    response = client.post(
        "/districts",
        json={"name": "Free State", "abbreviation": "FS2"},
    )
    assert response.status_code == 409

##-- GET /districts and GET /districts/{id} --##
def test_list_districts_empty(client):
    response = client.get("/districts")
    assert response.status_code == 200
    assert response.json() == []

def test_list_districts_returns_all_districts(client, db_session):
    make_district(db_session, name="District One", abbreviation="D1")
    make_district(db_session, name="District Two", abbreviation="D2")

    response = client.get("/districts")

    assert response.status_code == 200
    assert len(response.json()) == 2

def test_get_district_returns_one_district(client, db_session):
    district = make_district(db_session, name="Read District", abbreviation="RD")

    response = client.get(f"/districts/{district.id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": district.id,
        "name": district.name,
        "abbreviation": district.abbreviation,
    }

def test_get_district_not_found(client):
    response = client.get("/districts/9999")
    assert response.status_code == 404

##-- PATCH /districts/{id} --##
def test_update_district_success(client, db_session):
    district = make_district(db_session, name="Old District", abbreviation="OD")

    response = client.patch(
        f"/districts/{district.id}",
        json={"name": "Updated District", "abbreviation": "UD"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Updated District"
    assert body["abbreviation"] == "UD"
    assert body["id"] == district.id

def test_update_district_name(client, db_session):
    district = make_district(db_session, name="Old District", abbreviation="OD")

    response = client.patch(
        f"/districts/{district.id}",
        json={"name": "Updated District"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Updated District"
    assert body["abbreviation"] == "OD"  # unchanged
    assert body["id"] == district.id

def test_update_district_abbreviation(client, db_session):
    district = make_district(db_session, name="Old District", abbreviation="OD")

    response = client.patch(
        f"/districts/{district.id}",
        json={"abbreviation": "UD"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Old District"  # unchanged
    assert body["abbreviation"] == "UD"
    assert body["id"] == district.id

def test_update_district_not_found(client):
    response = client.patch(
        "/districts/9999",
        json={"name": "Nonexistent District", "abbreviation": "ND"},
    )
    assert response.status_code == 404

def test_update_district_duplicate_name(client, db_session):
    # Create two districts
    make_district(db_session, name="First District", abbreviation="FD")
    second = make_district(db_session, name="Second District", abbreviation="SD")

    response = client.patch(
        f"/districts/{second.id}",
        json={"name": "First District"},  # duplicate name
    )
    assert response.status_code == 409

def test_update_district_empty_body_noop(client, db_session):
    district = make_district(db_session, name="Empty District", abbreviation="ED")

    # The router has exclude_unset=True, so sending an empty body is a valid no-op. It should return 200 and not change anything.
    response = client.patch(f"/districts/{district.id}", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Empty District"
    assert body["abbreviation"] == "ED"

##-- DELETE /districts/{id} --##
def test_delete_district_success(client, db_session):
    district = make_district(db_session, name="Delete District", abbreviation="DD")

    response = client.delete(f"/districts/{district.id}")

    assert response.status_code == 204

    assert client.get(f"/districts/{district.id}").status_code == 404

def test_delete_district_not_found(client):
    response = client.delete("/districts/9999")
    assert response.status_code == 404

def test_delete_district_with_clubs(client, db_session):
    district = make_district(db_session)
    make_club(db_session, district=district)

    response = client.delete(f"/districts/{district.id}")

    assert response.status_code == 409
