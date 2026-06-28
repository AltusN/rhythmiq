"""
    Test cases for the gymnast router.
    Key differences from other routers:
    - Gymnasts are associated with clubs, so we need to create a club first before creating a gymnast.
    - Gymnasts have a unique constraint on the combination of first_name, last_name, and club_id.
    - Gymnasts can be filtered by club_id when listing  gymnasts.
"""

from test.conftest import make_club, make_district, make_gymnast


def test_create_gymnast_happy_path(client, db_session):
    # Create a district and a club first
    district = make_district(db_session)
    club = make_club(db_session, district)

    response = client.post(
        "/gymnasts",
        json={
            "club_id": club.id,
            "first_name": "Dina",
            "last_name": "Averina",
            "date_of_birth": "2008-12-01",
            "country_code": "RUS",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["club_id"] == club.id
    assert body["first_name"] == "Dina"
    assert body["last_name"] == "Averina"
    assert body["date_of_birth"] == "2008-12-01"
    assert body["country_code"] == "RUS"
    assert "id" in body

def test_create_gymnast_independent(client, db_session):
    # club_id is optional, so we can create a gymnast without a club
    response = client.post(
        "/gymnasts",
        json={
            "first_name": "Dina",
            "last_name": "Averina",
            "date_of_birth": "2008-12-01",
            "country_code": "RUS",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["club_id"] is None
    assert "id" in body

def test_create_gymnast_minimal_data(client, db_session):
    # Only first_name and last_name are required
    response = client.post(
        "/gymnasts",
        json={
            "first_name": "Dina",
            "last_name": "Averina",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["first_name"] == "Dina"
    assert body["last_name"] == "Averina"
    assert body["date_of_birth"] is None
    assert body["country_code"] is None
    assert body["club_id"] is None
    assert "id" in body

def test_gymnast_create_club_not_found(client, db_session):
    response = client.post(
        "/gymnasts",
        json={
            "club_id": 9999,  # Non-existent club ID
            "first_name": "Dina",
            "last_name": "Averina",
        },
    )
    assert response.status_code == 404
    assert "club" in response.json()["detail"].lower()

def test_create_gymnast_duplicate(client, db_session):
    # Create a district and a club first
    district = make_district(db_session)
    club = make_club(db_session, district)

    # Create the first gymnast
    make_gymnast(
        db_session,
        club=club,
        first_name="Dina",
        last_name="Averina",
    )

    # Attempt to create a duplicate gymnast
    response = client.post(
        "/gymnasts",
        json={
            "club_id": club.id,
            "first_name": "Dina",
            "last_name": "Averina",
            "date_of_birth": "2016-10-01",
        },
    )
    assert response.status_code == 409

def test_gymnast_create_country_upppercase(client, db_session):
    response = client.post(
        "/gymnasts",
        json={
            "first_name": "Dina",
            "last_name": "Averina",
            "country_code": "rus",  # Lowercase country code
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["country_code"] == "RUS"  # Should be stored as uppercase

def test_gymnast_create_country_invalid(client, db_session):
    response = client.post(
        "/gymnasts",
        json={
            "first_name": "Dina",
            "last_name": "Averina",
            "country_code": "INVALID",  # Invalid country code
        },
    )
    assert response.status_code == 422

def test_gymnast_create_whitespace(client, db_session):
    response = client.post(
        "/gymnasts",
        json={
            "first_name": "  Dina  ",
            "last_name": "  Averina  ",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["first_name"] == "Dina"
    assert body["last_name"] == "Averina"

def test_gymnast_create_invalid_date(client, db_session):
    response = client.post(
        "/gymnasts",
        json={
            "first_name": "Dina",
            "last_name": "Averina",
            "date_of_birth": "invalid-date",  # Invalid date format
        },
    )
    assert response.status_code == 422

##-- GET /gymnasts and GET /gymnasts/{id} --##
def test_list_gymnasts_empty(client):
    response = client.get("/gymnasts")
    assert response.status_code == 200
    assert response.json() == []

def test_list_gymnasts_returns_all_gymnasts(client, db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    make_gymnast(db_session, club=club, first_name="Dina", last_name="Averina")
    make_gymnast(db_session, club=club, first_name="Arina", last_name="Averina")

    response = client.get("/gymnasts")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2

def test_list_gymnasts_filter_by_club(client, db_session):
    district = make_district(db_session)
    club1 = make_club(db_session, district, name="Club One")
    club2 = make_club(db_session, district, name="Club Two")

    make_gymnast(db_session, club=club1, first_name="Dina", last_name="Averina")
    make_gymnast(db_session, club=club2, first_name="Arina", last_name="Averina")

    response = client.get(f"/gymnasts?club_id={club1.id}")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["first_name"] == "Dina"

def test_list_gymnasts_include_independent(client, db_session):
    make_gymnast(db_session, first_name="Dina", last_name="Averina")
    make_gymnast(db_session, first_name="Arina", last_name="Averina", club=None)

    response = client.get("/gymnasts")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2

def test_get_gymnast_returns_one_gymnast(client, db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    gymnast = make_gymnast(db_session, club=club, first_name="Dina", last_name="Averina")

    response = client.get(f"/gymnasts/{gymnast.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == gymnast.id
    assert body["first_name"] == "Dina"
    assert body["last_name"] == "Averina"

def test_get_gymnast_not_found(client):
    response = client.get("/gymnasts/9999")
    assert response.status_code == 404

##-- Patch /gymnasts/{id} --##
def test_update_gymnast_success(client, db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    gymnast = make_gymnast(db_session, club=club, first_name="Dina", last_name="Averina")

    response = client.patch(
        f"/gymnasts/{gymnast.id}",
        json={"first_name": "Updated Dina", "last_name": "Updated Averina"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "Updated Dina"
    assert body["last_name"] == "Updated Averina"

def test_update_gymnast_club(client, db_session):
    district = make_district(db_session)
    club1 = make_club(db_session, district, name="Club One")
    club2 = make_club(db_session, district, name="Club Two")
    gymnast = make_gymnast(db_session, club=club1, first_name="Dina", last_name="Averina")

    response = client.patch(
        f"/gymnasts/{gymnast.id}",
        json={"club_id": club2.id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["club_id"] == club2.id

def test_update_gymnast_make_independent(client, db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    gymnast = make_gymnast(db_session, club=club, first_name="Dina", last_name="Averina")

    response = client.patch(
        f"/gymnasts/{gymnast.id}",
        json={"club_id": None},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["club_id"] is None

def test_update_gymnast_not_found(client):
    response = client.patch(
        "/gymnasts/9999",
        json={"first_name": "Updated Dina"},
    )
    assert response.status_code == 404

def test_update_gymnast_club_not_found(client, db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    gymnast = make_gymnast(db_session, club=club, first_name="Dina", last_name="Averina")

    response = client.patch(
        f"/gymnasts/{gymnast.id}",
        json={"club_id": 9999},  # Non-existent club ID
    )
    assert response.status_code == 404
    assert "club" in response.json()["detail"].lower()

def test_update_gymnast_duplicate(client, db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)

    # Create two gymnasts
    make_gymnast(db_session, club=club, first_name="Dina", last_name="Averina")
    gymnast2 = make_gymnast(db_session, club=club, first_name="Arina", last_name="Averina")

    # Attempt to update gymnast2 to have the same name as gymnast1
    response = client.patch(
        f"/gymnasts/{gymnast2.id}",
        json={"first_name": "Dina", "last_name": "Averina"},
    )
    assert response.status_code == 409

def test_update_gymnast_body_is_empty(client, db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    gymnast = make_gymnast(db_session, club=club, first_name="Dina", last_name="Averina")

    response = client.patch(
        f"/gymnasts/{gymnast.id}",
        json={},  # Empty body
    )
    assert response.status_code == 200


##-- Delete /gymnasts/{id} --##
def test_delete_gymnast_success(client, db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    gymnast = make_gymnast(db_session, club=club, first_name="Dina", last_name="Averina")

    response = client.delete(f"/gymnasts/{gymnast.id}")
    assert response.status_code == 204

    # Verify that the gymnast is actually deleted
    get_response = client.get(f"/gymnasts/{gymnast.id}")
    assert get_response.status_code == 404

def test_delete_gymnast_not_found(client):
    response = client.delete("/gymnasts/9999")
    assert response.status_code == 404
