"""
    Test cases for the gymnast router.
    Key differences from other routers:
    - Gymnasts are associated with clubs, so we need to create a club first before creating a gymnast.
    - Gymnasts have a unique constraint on the combination of first_name, last_name, and club_id.
    - Gymnasts can be filtered by club_id when listing  gymnasts.
"""

from test.conftest import make_club, make_district, make_group, make_gymnast


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


def test_create_gymnast_with_group_success(client, db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    group = make_group(db_session, club=club, name="Junior Group A")

    response = client.post(
        "/gymnasts",
        json={
            "club_id": club.id,
            "group_id": group.id,
            "first_name": "Lala",
            "last_name": "Kramarenko",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["club_id"] == club.id
    assert body["group_id"] == group.id


def test_create_gymnast_with_group_no_club_success(client, db_session):
    # Independent gymnasts (no club) can still belong to a group.
    district = make_district(db_session)
    club = make_club(db_session, district)
    group = make_group(db_session, club=club, name="Junior Group B")

    response = client.post(
        "/gymnasts",
        json={
            "group_id": group.id,
            "first_name": "Alina",
            "last_name": "Kabaeva",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["club_id"] is None
    assert body["group_id"] == group.id


def test_create_gymnast_group_not_found(client, db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)

    response = client.post(
        "/gymnasts",
        json={
            "club_id": club.id,
            "group_id": 9999,
            "first_name": "Dina",
            "last_name": "Averina",
        },
    )

    assert response.status_code == 404
    assert "group" in response.json()["detail"].lower()


def test_create_gymnast_group_club_mismatch_rejected(client, db_session):
    district = make_district(db_session)
    club1 = make_club(db_session, district, name="Club One")
    club2 = make_club(db_session, district, name="Club Two")
    group2 = make_group(db_session, club=club2, name="Group Two")

    response = client.post(
        "/gymnasts",
        json={
            "club_id": club1.id,
            "group_id": group2.id,
            "first_name": "Arina",
            "last_name": "Averina",
        },
    )

    assert response.status_code == 409
    assert "group" in response.json()["detail"].lower()

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


def test_update_gymnast_group_success(client, db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    group = make_group(db_session, club=club, name="Senior Group A")
    gymnast = make_gymnast(db_session, club=club, first_name="Dina", last_name="Averina")

    response = client.patch(
        f"/gymnasts/{gymnast.id}",
        json={"group_id": group.id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["group_id"] == group.id


def test_update_gymnast_clear_group(client, db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    group = make_group(db_session, club=club, name="Senior Group B")
    gymnast = make_gymnast(
        db_session,
        club=club,
        group=group,
        first_name="Arina",
        last_name="Averina",
    )

    response = client.patch(
        f"/gymnasts/{gymnast.id}",
        json={"group_id": None},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["group_id"] is None


def test_update_gymnast_group_not_found(client, db_session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    gymnast = make_gymnast(db_session, club=club, first_name="Dina", last_name="Averina")

    response = client.patch(
        f"/gymnasts/{gymnast.id}",
        json={"group_id": 9999},
    )

    assert response.status_code == 404
    assert "group" in response.json()["detail"].lower()


def test_update_gymnast_group_club_mismatch_rejected(client, db_session):
    district = make_district(db_session)
    club1 = make_club(db_session, district, name="Club One")
    club2 = make_club(db_session, district, name="Club Two")
    group2 = make_group(db_session, club=club2, name="Group Two")
    gymnast = make_gymnast(db_session, club=club1, first_name="Dina", last_name="Averina")

    response = client.patch(
        f"/gymnasts/{gymnast.id}",
        json={"group_id": group2.id},
    )

    assert response.status_code == 409
    assert "group" in response.json()["detail"].lower()


def test_update_gymnast_club_conflicts_with_existing_group(client, db_session):
    district = make_district(db_session)
    club1 = make_club(db_session, district, name="Club One")
    club2 = make_club(db_session, district, name="Club Two")
    group1 = make_group(db_session, club=club1, name="Group One")
    gymnast = make_gymnast(
        db_session,
        club=club1,
        group=group1,
        first_name="Arina",
        last_name="Averina",
    )

    response = client.patch(
        f"/gymnasts/{gymnast.id}",
        json={"club_id": club2.id},
    )

    assert response.status_code == 409
    assert "group" in response.json()["detail"].lower()

def test_update_gymnast_clear_club_keeps_group(client, db_session):
    # A gymnast can drop club membership while remaining in the club's group
    # (e.g. going independent) — the group/club mismatch check should not
    # fire when club_id is being cleared, not conflicted.
    district = make_district(db_session)
    club = make_club(db_session, district)
    group = make_group(db_session, club=club, name="Senior Group C")
    gymnast = make_gymnast(
        db_session,
        club=club,
        group=group,
        first_name="Alina",
        last_name="Kabaeva",
    )

    response = client.patch(
        f"/gymnasts/{gymnast.id}",
        json={"club_id": None},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["club_id"] is None
    assert body["group_id"] == group.id


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


def test_create_gymnast_with_ethnicity_and_gsa_number(client, db_session):
    response = client.post(
        "/gymnasts",
        json={
            "first_name": "Dina",
            "last_name": "Averina",
            "date_of_birth": "2008-12-01",
            "ethnicity": "indian",
            "gsa_number": "GSA-1001",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["ethnicity"] == "indian"
    assert body["gsa_number"] == "GSA-1001"


def test_create_gymnast_without_new_fields_returns_nulls(client, db_session):
    response = client.post(
        "/gymnasts",
        json={"first_name": "Dina", "last_name": "Averina", "date_of_birth": "2008-12-01"},
    )

    assert response.status_code == 201
    assert response.json()["ethnicity"] is None
    assert response.json()["gsa_number"] is None


def test_create_gymnast_rejects_unknown_ethnicity(client, db_session):
    response = client.post(
        "/gymnasts",
        json={"first_name": "Dina", "last_name": "Averina", "ethnicity": "martian"},
    )

    assert response.status_code == 422


def test_update_gymnast_ethnicity_and_gsa_number(client, db_session):
    gymnast = make_gymnast(db_session, first_name="Patch", last_name="Target")

    response = client.patch(
        f"/gymnasts/{gymnast.id}",
        json={"ethnicity": "prefer_not_to_say", "gsa_number": "GSA-2002"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ethnicity"] == "prefer_not_to_say"
    assert body["gsa_number"] == "GSA-2002"


def test_update_gymnast_can_clear_gsa_number(client, db_session):
    gymnast = make_gymnast(db_session, first_name="Clear", last_name="Target")

    response = client.patch(f"/gymnasts/{gymnast.id}", json={"gsa_number": ""})

    assert response.status_code == 200
    assert response.json()["gsa_number"] is None


def test_create_gymnast_duplicate_gsa_number_returns_409(client, db_session):
    first = client.post(
        "/gymnasts",
        json={"first_name": "Owner", "last_name": "OfNumber", "gsa_number": "GSA-DUP"},
    )
    assert first.status_code == 201

    response = client.post(
        "/gymnasts",
        json={"first_name": "Other", "last_name": "Person", "gsa_number": "GSA-DUP"},
    )

    assert response.status_code == 409
    assert "GSA" in response.json()["detail"]


def test_update_gymnast_duplicate_gsa_number_returns_409(client, db_session):
    # Stands alone: the router-test fixture shares one transaction per test, so a
    # 409's db.rollback() here would undo any commits made earlier in the same test.
    owner = client.post(
        "/gymnasts",
        json={"first_name": "Owner", "last_name": "OfNumber", "gsa_number": "GSA-PATCH-DUP"},
    )
    assert owner.status_code == 201

    other = client.post(
        "/gymnasts",
        json={"first_name": "Other", "last_name": "Gymnast", "gsa_number": "GSA-OWN-2"},
    )
    assert other.status_code == 201
    other_id = other.json()["id"]

    response = client.patch(
        f"/gymnasts/{other_id}",
        json={"gsa_number": "GSA-PATCH-DUP"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "A gymnast with GSA number 'GSA-PATCH-DUP' already exists"
