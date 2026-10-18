"""今日三件事（MIT）测试。"""

import app as app_module


def _create(client, title):
    return client.post("/api/todos", json={"title": title}).get_json()["id"]


def test_mit_limit_and_list(auth_client):
    ids = [_create(auth_client, "任务%d" % index) for index in range(4)]

    for todo_id in ids[:3]:
        assert (
            auth_client.put(
                f"/api/todos/{todo_id}/mit", json={"is_mit": True}
            ).status_code
            == 200
        )
    assert (
        auth_client.put(f"/api/todos/{ids[3]}/mit", json={"is_mit": True}).status_code
        == 400
    )

    mit = auth_client.get("/api/todos/mit").get_json()
    assert len(mit) == 3
    assert all(item["is_mit"] for item in mit)

    stats = auth_client.get("/api/todos/stats").get_json()
    assert stats["mit_pending"] == 3
    assert stats["mit_completed"] == 0


def test_unset_mit(auth_client):
    todo_id = _create(auth_client, "任务")
    auth_client.put(f"/api/todos/{todo_id}/mit", json={"is_mit": True})
    assert len(auth_client.get("/api/todos/mit").get_json()) == 1

    response = auth_client.put(
        f"/api/todos/{todo_id}/mit", json={"is_mit": False}
    )
    assert response.status_code == 200
    assert auth_client.get("/api/todos/mit").get_json() == []


def test_completed_mit_stats(auth_client):
    todo_id = _create(auth_client, "任务")
    auth_client.put(f"/api/todos/{todo_id}/mit", json={"is_mit": True})
    auth_client.put(f"/api/todos/{todo_id}", json={"completed": True})

    mit = auth_client.get("/api/todos/mit").get_json()
    assert mit[0]["completed"] is True

    stats = auth_client.get("/api/todos/stats").get_json()
    assert stats["mit_completed"] == 1
    assert stats["mit_pending"] == 0


def test_mit_isolation(auth_client):
    todo_id = _create(auth_client, "私有")

    other = app_module.app.test_client()
    other.post(
        "/api/register",
        json={
            "username": "bob",
            "password": "secret123",
            "email": "bob@example.com",
        },
    )
    other.post("/api/login", json={"username": "bob", "password": "secret123"})

    assert (
        other.put(
            f"/api/todos/{todo_id}/mit", json={"is_mit": True}
        ).status_code
        == 404
    )
    assert other.get("/api/todos/mit").get_json() == []


def test_mit_validation(auth_client):
    todo_id = _create(auth_client, "任务")
    assert (
        auth_client.put(
            f"/api/todos/{todo_id}/mit", json={"is_mit": "yes"}
        ).status_code
        == 400
    )
