"""登录失败限流与账户锁定测试。"""

import app as app_module


def _register(client, username="alice"):
    client.post(
        "/api/register",
        json={
            "username": username,
            "password": "secret123",
            "email": f"{username}@example.com",
        },
    )


def test_login_locks_after_failures(client):
    _register(client)

    for _ in range(5):
        response = client.post(
            "/api/login", json={"username": "alice", "password": "wrong"}
        )
        assert response.status_code == 401

    response = client.post(
        "/api/login", json={"username": "alice", "password": "secret123"}
    )
    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_login_success_resets_failures(client):
    _register(client)

    for _ in range(4):
        client.post("/api/login", json={"username": "alice", "password": "wrong"})

    assert (
        client.post(
            "/api/login", json={"username": "alice", "password": "secret123"}
        ).status_code
        == 200
    )
    client.post("/api/logout")

    for _ in range(4):
        assert (
            client.post(
                "/api/login", json={"username": "alice", "password": "wrong"}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/login", json={"username": "alice", "password": "wrong"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/login", json={"username": "alice", "password": "secret123"}
        ).status_code
        == 429
    )


def test_admin_can_unlock_user(admin_client):
    response = admin_client.post(
        "/api/admin/users",
        json={
            "username": "alice",
            "password": "secret123",
            "email": "alice@example.com",
        },
    )
    assert response.status_code == 201
    alice_id = response.get_json()["id"]

    alice = app_module.app.test_client()
    for _ in range(5):
        alice.post("/api/login", json={"username": "alice", "password": "wrong"})
    assert (
        alice.post(
            "/api/login", json={"username": "alice", "password": "secret123"}
        ).status_code
        == 429
    )

    users = admin_client.get("/api/admin/users").get_json()["users"]
    target = next(item for item in users if item["id"] == alice_id)
    assert target["locked"] is True

    assert (
        admin_client.post(f"/api/admin/users/{alice_id}/unlock").status_code == 200
    )
    assert (
        alice.post(
            "/api/login", json={"username": "alice", "password": "secret123"}
        ).status_code
        == 200
    )

    actions = [
        item["action"]
        for item in admin_client.get("/api/admin/audit-logs").get_json()
    ]
    assert "login_locked" in actions
    assert "unlock_user" in actions
