""" Test suite for the coach router. 
    Coach is under club. Nothing special about coach
    but, you can't create a coach without a club, so we need to make sure
    that the club exists before creating a coach.
"""
from fastapi.testclient import TestClient
from sqlalchemy.orm.session import Session

from test.conftest import make_club, make_coach, make_district

##-- POST /coaches --##
def test_create_coach_happy_path(client: TestClient, db_session: Session):
    district = make_district(db_session)
    club = make_club(db_session, district)

    response = client.post(
        "/coaches",
        json={
            "club_id": club.id,
            "first_name": "John",
            "last_name": "Doe",
            "is_head_coach": True,
        }
    )

    assert response.status_code == 201
    body = response.json()
    assert body["first_name"] == "John"
    assert body["last_name"] == "Doe"
    assert body["is_head_coach"] is True
    assert body["club_id"] == club.id

def test_create_coach_head_coach_defaults_to_false(client: TestClient, db_session: Session):
    district = make_district(db_session)
    club = make_club(db_session, district)

    response = client.post(
        "/coaches",
        json={
            "club_id": club.id,
            "first_name": "Jane",
            "last_name": "Smith",
        }
    )

    assert response.status_code == 201
    body = response.json()
    assert body["first_name"] == "Jane"
    assert body["last_name"] == "Smith"
    assert body["is_head_coach"] is False
    assert body["club_id"] == club.id

def test_create_coach_with_spaces_in_name(client: TestClient, db_session: Session):
    district = make_district(db_session)
    club = make_club(db_session, district)

    response = client.post(
        "/coaches",
        json={
            "club_id": club.id,
            "first_name": "  Alice  ",
            "last_name": "  Johnson  ",
        }
    )

    assert response.status_code == 201
    body = response.json()
    assert body["first_name"] == "Alice"
    assert body["last_name"] == "Johnson"

def test_create_coach_with_spaces_in_surname(client: TestClient, db_session: Session):
    district = make_district(db_session)
    club = make_club(db_session, district)

    response = client.post(
        "/coaches",
        json={
            "club_id": club.id,
            "first_name": "Bob",
            "last_name": "  Smith  ",
        }
    )

    assert response.status_code == 201
    body = response.json()
    assert body["first_name"] == "Bob"
    assert body["last_name"] == "Smith"

def test_create_coach_strips_whitespace(client: TestClient, db_session: Session):
    district = make_district(db_session)
    club = make_club(db_session, district)

    response = client.post(
        "/coaches",
        json={
            "club_id": club.id,
            "first_name": "  Charlie  ",
            "last_name": "  Brown  ",
        }
    )

    assert response.status_code == 201
    body = response.json()
    assert body["first_name"] == "Charlie"
    assert body["last_name"] == "Brown"

def test_create_coach_with_nonexistent_club(client: TestClient, db_session: Session):
    """ Explicit 404 before inserting into the DB. This is a better user experience than a generic 500 from the DB. """
    response = client.post(
        "/coaches",
        json={
            "club_id": 9999,  # Non-existent club ID
            "first_name": "David",
            "last_name": "Wilson",
        }
    )

    assert response.status_code == 404
    body = response.json()
    assert body["detail"] == "Club with id 9999 not found"

def test_create_duplicate_coach_for_club_fails(client: TestClient, db_session: Session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    make_coach(db_session, first_name="Eve", last_name="Taylor", club=club)

    response = client.post(
        "/coaches",
        json={
            "club_id": club.id,
            "first_name": "Eve",
            "last_name": "Taylor",
        }
    )

    assert response.status_code == 409
    body = response.json()
    assert body["detail"] == f"Coach with name 'Eve Taylor' already exists in club {club.id}"

##-- Get /coaches and GET /coaches/{id} --##
def test_list_coaches_empty(client: TestClient):
    response = client.get("/coaches")
    assert response.status_code == 200
    assert response.json() == []

def test_list_coaches_returns_all_coaches(client: TestClient, db_session: Session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    coach_1 = make_coach(db_session, first_name="Frank", last_name="Miller", club=club)
    coach_2 = make_coach(db_session, first_name="Grace", last_name="Lee", club=club)

    response = client.get("/coaches")
    body = response.json()
    assert response.status_code == 200
    assert len(body) == 2
    assert any(coach["id"] == coach_1.id for coach in body)
    assert any(coach["id"] == coach_2.id for coach in body)

def test_get_coach_returns_one_coach(client: TestClient, db_session: Session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    coach = make_coach(db_session, first_name="Hannah", last_name="Davis", club=club)

    response = client.get(f"/coaches/{coach.id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": coach.id,
        "first_name": coach.first_name,
        "last_name": coach.last_name,
        "is_head_coach": coach.is_head_coach,
        "club_id": club.id,
    }

def test_list_coaches_filtered_by_club(client: TestClient, db_session: Session):
    district = make_district(db_session)
    club_1 = make_club(db_session, district, name="Club One", abbreviation="C1")
    club_2 = make_club(db_session, district, name="Club Two", abbreviation="C2")

    coach_1 = make_coach(db_session, first_name="Ian", last_name="Scott", club=club_1)
    coach_2 = make_coach(db_session, first_name="Jack", last_name="Adams", club=club_2)

    response = client.get(f"/coaches?club_id={club_1.id}")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == coach_1.id

def test_get_coach_success(client: TestClient, db_session: Session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    coach = make_coach(db_session, first_name="Karen", last_name="White", club=club)

    response = client.get(f"/coaches/{coach.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == coach.id
    assert body["first_name"] == "Karen"
    assert body["last_name"] == "White"
    assert body["club_id"] == club.id

def test_get_coach_not_found(client: TestClient):
    response = client.get("/coaches/9999")
    assert response.status_code == 404
    body = response.json()
    assert body["detail"] == "Coach with id 9999 not found"

##-- Patch /coaches/{id} --##
def test_update_coach_success(client: TestClient, db_session: Session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    coach = make_coach(db_session, first_name="Liam", last_name="Johnson", club=club)

    response = client.patch(
        f"/coaches/{coach.id}",
        json={"first_name": "Liam Updated", "last_name": "Johnson Updated", "is_head_coach": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "Liam Updated"
    assert body["last_name"] == "Johnson Updated"
    assert body["is_head_coach"] is True

def test_update_coach_is_head_coach(client: TestClient, db_session: Session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    coach = make_coach(db_session, first_name="Mia", last_name="Brown", club=club)

    response = client.patch(
        f"/coaches/{coach.id}",
        json={"is_head_coach": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_head_coach"] is True

def test_update_coach_not_found(client: TestClient):
    response = client.patch(
        "/coaches/9999",
        json={"first_name": "Nonexistent", "last_name": "Coach"},
    )
    assert response.status_code == 404
    body = response.json()
    assert body["detail"] == "Coach with id 9999 not found"

def test_update_coach_duplicate_name(client: TestClient, db_session: Session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    coach_1 = make_coach(db_session, first_name="Noah", last_name="Davis", club=club)
    coach_2 = make_coach(db_session, first_name="Olivia", last_name="Miller", club=club)

    response = client.patch(
        f"/coaches/{coach_2.id}",
        json={"first_name": "Noah", "last_name": "Davis"},
    )

    assert response.status_code == 409
    body = response.json()
    assert body["detail"] == f"Coach with name 'Noah Davis' already exists in club {club.id}"

def test_update_coach_strips_whitespace(client: TestClient, db_session: Session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    coach = make_coach(db_session, first_name="Sophia", last_name="Wilson", club=club)

    response = client.patch(
        f"/coaches/{coach.id}",
        json={"first_name": "  Sophia Updated  ", "last_name": "  Wilson Updated  "},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "Sophia Updated"
    assert body["last_name"] == "Wilson Updated"

def test_update_coach_empty_body(client: TestClient, db_session: Session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    coach = make_coach(db_session, first_name="Ava", last_name="Martinez", club=club)

    response = client.patch(f"/coaches/{coach.id}", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "Ava"
    assert body["last_name"] == "Martinez"

def test_update_coach_partial_fields(client: TestClient, db_session: Session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    coach = make_coach(db_session, first_name="Ethan", last_name="Anderson", club=club)

    response = client.patch(
        f"/coaches/{coach.id}",
        json={"first_name": "Ethan Updated"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "Ethan Updated"
    assert body["last_name"] == "Anderson"  # unchanged

def test_delete_coach_success(client: TestClient, db_session: Session):
    district = make_district(db_session)
    club = make_club(db_session, district)
    coach = make_coach(db_session, first_name="Lily", last_name="Thomas", club=club)

    response = client.delete(f"/coaches/{coach.id}")

    assert response.status_code == 204

    # Verify that the coach is actually deleted
    get_response = client.get(f"/coaches/{coach.id}")
    assert get_response.status_code == 404

def test_delete_coach_not_found(client: TestClient):
    response = client.delete("/coaches/9999")
    assert response.status_code == 404
    body = response.json()
    assert body["detail"] == "Coach with id 9999 not found"