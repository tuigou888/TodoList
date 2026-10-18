"""管理员权限、用户管理与审计日志测试。"""

import app as app_module


def test_admin_required(client):
    client.post(
        "/api/register",
        json={
            "username": "alice",
            "password": "secret123",
            "email": "alice@example.com",
        },
    )
    client.post("/api/login", json={"username": "alice", "password": "secret123"})
    assert client.get("/api/admin/users").status_code == 403


def test_admin_stats(admin_client):
    response = admin_client.get("/api/admin/stats")
    assert response.status_code == 200
    data = response.get_json()
    assert data["users_total"] == 1
    assert data["admins"] == 1


def test_admin_user_lifecycle(admin_client):
    response = admin_client.post(
        "/api/admin/users",
        json={
            "username": "bob",
            "password": "bobpass123",
            "email": "bob@example.com",
        },
    )
    assert response.status_code == 201
    bob_id = response.get_json()["id"]

    response = admin_client.put(
        f"/api/admin/users/{bob_id}",
        json={"email": "bob2@example.com", "is_active": False},
    )
    assert response.status_code == 200

    bob = app_module.app.test_client()
    assert (
        bob.post(
            "/api/login", json={"username": "bob", "password": "bobpass123"}
        ).status_code
        == 403
    )

    logs = admin_client.get("/api/admin/audit-logs").get_json()
    assert any(item["action"] == "update_user" for item in logs)

    assert admin_client.delete(f"/api/admin/users/{bob_id}").status_code == 200
    assert (
        admin_client.delete(f"/api/admin/users/{bob_id}").status_code == 404
    )


def test_admin_cannot_delete_or_demote_self(admin_client):
    me = admin_client.get("/api/me").get_json()
    assert admin_client.delete(f"/api/admin/users/{me['id']}").status_code == 400
    assert (
        admin_client.put(
            f"/api/admin/users/{me['id']}", json={"is_admin": False}
        ).status_code
        == 400
    )
    assert (
        admin_client.put(
            f"/api/admin/users/{me['id']}", json={"is_active": False}
        ).status_code
        == 400
    )


def test_admin_pagination_is_clamped(admin_client):
    assert (
        admin_client.get("/api/admin/users?per_page=99999")
        .get_json()["per_page"]
        == 100
    )
    assert (
        admin_client.get("/api/admin/users?per_page=-5").get_json()["per_page"] == 1
    )
    assert admin_client.get("/api/admin/users?page=-3").get_json()["page"] == 1


def test_delete_user_cascades_todos_and_sessions(admin_client, db):
    response = admin_client.post(
        "/api/admin/users",
        json={
            "username": "bob",
            "password": "bobpass123",
            "email": "bob@example.com",
        },
    )
    bob_id = response.get_json()["id"]

    bob = app_module.app.test_client()
    bob.post("/api/login", json={"username": "bob", "password": "bobpass123"})
    assert bob.post("/api/todos", json={"title": "bob 任务"}).status_code == 201

    assert admin_client.delete(f"/api/admin/users/{bob_id}").status_code == 200
    remaining = db.execute(
        "SELECT COUNT(*) FROM todos WHERE user_id = ?", (bob_id,)
    ).fetchone()[0]
    assert remaining == 0
    assert bob.get("/api/me").status_code == 401


def test_admin_create_user_validation(admin_client):
    assert (
        admin_client.post(
            "/api/admin/users",
            json={"username": "a", "password": "secret123", "email": "a@example.com"},
        ).status_code
        == 400
    )
    assert (
        admin_client.post(
            "/api/admin/users",
            json={"username": "bob", "password": "123", "email": "b@example.com"},
        ).status_code
        == 400
    )
    assert (
        admin_client.post(
            "/api/admin/users",
            json={"username": "bob", "password": "secret123", "email": "nope"},
        ).status_code
        == 400
    )
