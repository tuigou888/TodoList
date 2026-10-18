"""待办事项 CRUD、筛选与统计测试。"""

import app as app_module


def test_add_todo_with_due_and_priority(auth_client):
    response = auth_client.post(
        "/api/todos",
        json={
            "title": "写报告",
            "description": "季度报告",
            "due_date": "2026-12-31",
            "priority": 3,
        },
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data["due_date"] == "2026-12-31"
    assert data["priority"] == 3
    assert data["completed"] is False
    assert data["completed_at"] is None


def test_add_todo_validation(auth_client):
    assert auth_client.post("/api/todos", json={"title": "  "}).status_code == 400
    assert auth_client.post("/api/todos", json={"title": 123}).status_code == 400
    assert (
        auth_client.post("/api/todos", json={"title": "x" * 201}).status_code == 400
    )
    assert (
        auth_client.post(
            "/api/todos", json={"title": "ok", "due_date": "2026-13-01"}
        ).status_code
        == 400
    )
    assert (
        auth_client.post(
            "/api/todos", json={"title": "ok", "priority": 9}
        ).status_code
        == 400
    )


def test_update_todo_fields(auth_client):
    todo_id = auth_client.post("/api/todos", json={"title": "任务"}).get_json()["id"]

    response = auth_client.put(
        f"/api/todos/{todo_id}",
        json={"title": "新标题", "due_date": "2026-11-11", "priority": 1},
    )
    assert response.status_code == 200
    assert response.get_json()["title"] == "新标题"
    assert response.get_json()["priority"] == 1

    response = auth_client.put(f"/api/todos/{todo_id}", json={"completed": True})
    assert response.get_json()["completed"] is True
    assert response.get_json()["completed_at"] is not None

    assert (
        auth_client.put(
            f"/api/todos/{todo_id}", json={"completed": "yes"}
        ).status_code
        == 400
    )
    assert (
        auth_client.put(f"/api/todos/{todo_id}", json={"title": " "}).status_code
        == 400
    )


def test_filters_and_search(auth_client):
    auth_client.post(
        "/api/todos",
        json={"title": "写报告", "priority": 3, "due_date": "2026-12-31"},
    )
    second = auth_client.post(
        "/api/todos", json={"title": "买牛奶", "priority": 1}
    ).get_json()["id"]
    auth_client.post(
        "/api/todos", json={"title": "打扫", "priority": 2, "due_date": "2026-10-01"}
    )
    auth_client.put(f"/api/todos/{second}", json={"completed": True})

    assert len(auth_client.get("/api/todos?view=all&status=completed").get_json()) == 1
    assert len(auth_client.get("/api/todos?view=all&priority=3").get_json()) == 1
    assert len(auth_client.get("/api/todos?view=all&q=报告").get_json()) == 1

    due_sorted = auth_client.get("/api/todos?view=all&sort=due_asc").get_json()
    assert due_sorted[0]["due_date"] == "2026-10-01"

    assert auth_client.get("/api/todos?date=bad").status_code == 400


def test_stats(auth_client):
    auth_client.post("/api/todos", json={"title": "a", "due_date": "2000-01-01"})
    auth_client.post("/api/todos", json={"title": "b"})

    stats = auth_client.get("/api/todos/stats").get_json()
    assert stats["total"] == 2
    assert stats["pending"] == 2
    assert stats["overdue"] == 1


def test_user_isolation(auth_client):
    todo_id = auth_client.post("/api/todos", json={"title": "私有"}).get_json()["id"]

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
            f"/api/todos/{todo_id}", json={"completed": True}
        ).status_code
        == 404
    )
    assert other.delete(f"/api/todos/{todo_id}").status_code == 404
    assert other.get("/api/todos?view=all").get_json() == []


def test_delete_todo(auth_client):
    todo_id = auth_client.post("/api/todos", json={"title": "任务"}).get_json()["id"]
    assert auth_client.delete(f"/api/todos/{todo_id}").status_code == 200
    assert auth_client.delete(f"/api/todos/{todo_id}").status_code == 404


def test_requires_login(client):
    assert client.get("/api/todos").status_code == 401
    assert client.post("/api/todos", json={"title": "x"}).status_code == 401
