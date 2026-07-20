"""
Test for the judge router. Test POST / GET / PATCH / DELETE endpoints for judges.
"""

from app.models import JudgeCategory
from test.conftest import make_judge, make_judge_score


##-- POST /judges --##
def test_create_judge_success(client):
    response = client.post(
        "/judges/",
        json={
            "first_name": "Jane",
            "last_name": "Fig",
            "country_code": "usa",
            "category": "category_1",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["first_name"] == "Jane"
    assert body["last_name"] == "Fig"
    assert body["country_code"] == "USA"  # stripped/uppercased by the schema validator
    assert body["category"] == "category_1"
    assert "id" in body


def test_create_judge_without_optional_fields(client):
    response = client.post("/judges/", json={"first_name": "John", "last_name": "Doe"})

    assert response.status_code == 201
    body = response.json()
    assert body["country_code"] is None
    assert body["category"] is None


def test_create_judge_invalid_country_code_returns_422(client):
    response = client.post(
        "/judges/",
        json={"first_name": "Jane", "last_name": "Fig", "country_code": "US"},
    )
    assert response.status_code == 422


def test_create_judge_duplicate_identity(client, db_session):
    make_judge(db_session, first_name="Dup", last_name="Licate", country_code="GBR")

    response = client.post(
        "/judges/",
        json={"first_name": "Dup", "last_name": "Licate", "country_code": "GBR"},
    )
    assert response.status_code == 409


def test_create_judge_same_name_different_country_allowed(client, db_session):
    make_judge(db_session, first_name="Alex", last_name="Kim", country_code="USA")

    response = client.post(
        "/judges/",
        json={"first_name": "Alex", "last_name": "Kim", "country_code": "CAN"},
    )
    assert response.status_code == 201


##-- GET /judges and GET /judges/{id} --##
def test_list_judges_empty(client):
    response = client.get("/judges/")
    assert response.status_code == 200
    assert response.json() == []


def test_list_judges_returns_all_judges(client, db_session):
    make_judge(db_session, first_name="Anna", last_name="Petrov", country_code="RUS")
    make_judge(db_session, first_name="Ben", last_name="Lee", country_code="KOR")

    response = client.get("/judges/")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_judges_filtered_by_country_code_match(client, db_session):
    make_judge(db_session, first_name="Anna", last_name="Petrov", country_code="RUS")
    make_judge(db_session, first_name="Ben", last_name="Lee", country_code="KOR")

    response = client.get("/judges/", params={"country_code": "RUS"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["last_name"] == "Petrov"


def test_list_judges_filtered_by_country_code_no_match(client, db_session):
    make_judge(db_session, first_name="Anna", last_name="Petrov", country_code="RUS")

    response = client.get("/judges/", params={"country_code": "ZZZ"})

    assert response.status_code == 200
    assert response.json() == []


def test_get_judge_returns_one_judge(client, db_session):
    judge = make_judge(db_session, first_name="Read", last_name="Judge", country_code="ESP")

    response = client.get(f"/judges/{judge.id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": judge.id,
        "first_name": "Read",
        "last_name": "Judge",
        "country_code": "ESP",
        "category": None,
    }


def test_get_judge_not_found(client):
    response = client.get("/judges/9999")
    assert response.status_code == 404


##-- PATCH /judges/{id} --##
def test_update_judge_success(client, db_session):
    judge = make_judge(
        db_session, first_name="Old", last_name="Name", category=JudgeCategory.category_2
    )

    response = client.patch(
        f"/judges/{judge.id}", json={"first_name": "New", "category": "category_1"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "New"
    assert body["last_name"] == "Name"  # unchanged
    assert body["category"] == "category_1"
    assert body["id"] == judge.id


def test_update_judge_rejects_a_category_outside_the_fig_scale(client, db_session):
    """
    The whole point of enumerating: free text let "Cat I", "level 3" and "1" all
    coexist for the same category. FIG defines exactly four.
    """
    judge = make_judge(db_session, category=JudgeCategory.category_2)

    response = client.patch(f"/judges/{judge.id}", json={"category": "International"})

    assert response.status_code == 422


def test_update_judge_can_clear_the_category(client, db_session):
    """
    NULL is meaningful, not just missing: the FIG scale only covers brevet holders,
    so a nationally-graded judge has no category to record.
    """
    judge = make_judge(db_session, category=JudgeCategory.category_2)

    response = client.patch(f"/judges/{judge.id}", json={"category": None})

    assert response.status_code == 200
    assert response.json()["category"] is None


def test_update_judge_not_found(client):
    response = client.patch("/judges/9999", json={"first_name": "Nobody"})
    assert response.status_code == 404


def test_update_judge_empty_body_noop(client, db_session):
    judge = make_judge(db_session, first_name="Static", last_name="Judge")

    # exclude_unset=True, so an empty body is a valid no-op
    response = client.patch(f"/judges/{judge.id}", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "Static"
    assert body["last_name"] == "Judge"


def test_update_judge_duplicate_identity(client, db_session):
    make_judge(db_session, first_name="First", last_name="Judge", country_code="USA")
    second = make_judge(db_session, first_name="Second", last_name="Judge", country_code="CAN")

    response = client.patch(
        f"/judges/{second.id}",
        json={
            "first_name": "First",
            "country_code": "USA",
        },  # collides with the first judge's identity
    )
    assert response.status_code == 409


##-- DELETE /judges/{id} --##
def test_delete_judge_success(client, db_session):
    judge = make_judge(db_session, first_name="Delete", last_name="Me")

    response = client.delete(f"/judges/{judge.id}")

    assert response.status_code == 204
    assert client.get(f"/judges/{judge.id}").status_code == 404


def test_delete_judge_not_found(client):
    response = client.delete("/judges/9999")
    assert response.status_code == 404


def test_delete_judge_with_scores_blocked(client, db_session):
    judge = make_judge(db_session, first_name="Scored", last_name="Judge")
    make_judge_score(db_session, judge=judge)

    response = client.delete(f"/judges/{judge.id}")

    assert response.status_code == 409
