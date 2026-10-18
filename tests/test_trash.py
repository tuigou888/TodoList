"""回收站、批量操作与导出测试。"""

import app as app_module


def _create(client, title="任务"):
    return client.post("/api/todos", json={"title": title}).get_json()["id"]


def test_soft_delete_and_trash_list(auth_client):
    todo_id = _create(auth_client)

    response = auth_client.delete(f"/api/todos/{todo_id}")
    assert response.status_code == 200
    assert auth_client.get("/api/todos?view=all").get_json() == []

    trash = auth_client.get("/api/todos?view=trash").get_json()
    assert len(trash) == 1
    assert trash[0]["deleted_at"]


def test_restore_and_purge(auth_client):
    todo_id = _create(auth_client)
    auth_client.delete(f"/api/todos/{todo_id}")

    assert auth_client.post(f"/api/todos/{todo_id}/restore").status_code == 200
    assert len(auth_client.get("/api/todos?view=all").get_json()) == 1

    auth_client.delete(f"/api/todos/{todo_id}")
    assert auth_client.delete(f"/api/todos/{todo_id}/purge").status_code == 200
    assert auth_client.get("/api/todos?view=trash").get_json() == []
    assert auth_client.delete(f"/api/todos/{todo_id}/purge").status_code == 404


def test_batch_actions(auth_client):
    ids = [_create(auth_client, "a"), _create(auth_client, "b")]

    response = auth_client.post(
        "/api/todos/batch", json={"ids": ids, "action": "complete"}
    )
    assert response.status_code == 200
    assert response.get_json()["updated"] == 2
    assert auth_client.get("/api/todos?view=all&status=active").get_json() == []

    response = auth_client.post(
        "/api/todos/batch", json={"ids": ids, "action": "delete"}
    )
    assert response.get_json()["updated"] == 2
    assert len(auth_client.get("/api/todos?view=trash").get_json()) == 2

    response = auth_client.post(
        "/api/todos/batch", json={"ids": ids, "action": "restore"}
    )
    assert response.get_json()["updated"] == 2

    response = auth_client.post(
        "/api/todos/batch",
        json={"ids": ids, "action": "priority", "priority": 3},
    )
    assert response.get_json()["updated"] == 2
    assert all(
        item["priority"] == 3
        for item in auth_client.get("/api/todos?view=all").get_json()
    )

    assert (
        auth_client.post(
            "/api/todos/batch", json={"ids": [], "action": "delete"}
        ).status_code
        == 400
    )
    assert (
        auth_client.post(
            "/api/todos/batch", json={"ids": [1, "x"], "action": "delete"}
        ).status_code
        == 400
    )
    assert (
        auth_client.post(
            "/api/todos/batch", json={"ids": [1], "action": "unknown"}
        ).status_code
        == 400
    )


def test_batch_isolation(auth_client):
    todo_id = _create(auth_client)

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

    response = other.post(
        "/api/todos/batch", json={"ids": [todo_id], "action": "complete"}
    )
    assert response.get_json()["updated"] == 0
    assert auth_client.get("/api/todos?view=all").get_json()[0]["completed"] is False


def test_stats_exclude_deleted(auth_client):
    todo_id = _create(auth_client)
    auth_client.delete(f"/api/todos/{todo_id}")

    stats = auth_client.get("/api/todos/stats").get_json()
    assert stats["total"] == 0
    assert stats["pending"] == 0


def test_export_csv_and_json(auth_client):
    _create(auth_client, "写报告")

    csv_response = auth_client.get("/api/todos/export?format=csv")
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["Content-Type"]
    assert "写报告" in csv_response.get_data(as_text=True)
    assert csv_response.headers["Content-Disposition"].startswith("attachment;")

    json_response = auth_client.get("/api/todos/export?format=json")
    assert json_response.status_code == 200
    assert json_response.get_json()[0]["title"] == "写报告"

    assert auth_client.get("/api/todos/export?format=xml").status_code == 400


def test_export_hides_deleted(auth_client):
    todo_id = _create(auth_client, "已删除")
    auth_client.delete(f"/api/todos/{todo_id}")

    response = auth_client.get("/api/todos/export?format=json")
    assert response.get_json() == []


def test_update_deleted_todo_is_rejected(auth_client):
    todo_id = _create(auth_client)
    auth_client.delete(f"/api/todos/{todo_id}")

    response = auth_client.put(f"/api/todos/{todo_id}", json={"title": "改标题"})
    assert response.status_code == 404
