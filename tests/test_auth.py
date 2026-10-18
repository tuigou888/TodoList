"""认证、密码与账号设置测试。"""

import re

import app as app_module
from todo_app.security import hash_password, legacy_hash_password


def test_register_and_login(client):
    response = client.post(
        "/api/register",
        json={
            "username": "alice",
            "password": "secret123",
            "email": "Alice@Example.com",
        },
    )
    assert response.status_code == 201
    assert response.get_json()["email"] == "alice@example.com"

    response = client.post(
        "/api/login", json={"username": "alice", "password": "secret123"}
    )
    assert response.status_code == 200
    assert client.get("/api/me").status_code == 200


def test_register_validation(client):
    assert (
        client.post(
            "/api/register",
            json={"username": "a", "password": "secret123", "email": "a@example.com"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/register",
            json={"username": "alice", "password": "123", "email": "a@example.com"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/register",
            json={"username": "alice", "password": "secret123", "email": "nope"},
        ).status_code
        == 400
    )


def test_duplicate_username_and_email_are_case_insensitive(client):
    client.post(
        "/api/register",
        json={
            "username": "Alice",
            "password": "secret123",
            "email": "Alice@Example.com",
        },
    )
    assert (
        client.post(
            "/api/register",
            json={
                "username": "alice",
                "password": "secret123",
                "email": "other@example.com",
            },
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/register",
            json={
                "username": "other",
                "password": "secret123",
                "email": "alice@example.com",
            },
        ).status_code
        == 400
    )


def test_password_hash_is_salted(db):
    db.execute(
        "INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
        ("u1", hash_password("samepass"), "u1@example.com"),
    )
    db.execute(
        "INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
        ("u2", hash_password("samepass"), "u2@example.com"),
    )
    db.commit()
    rows = db.execute("SELECT password FROM users ORDER BY id").fetchall()
    assert rows[0]["password"].startswith(("scrypt:", "pbkdf2:"))
    assert rows[0]["password"] != rows[1]["password"]


def test_legacy_hash_is_upgraded_on_login(client, db):
    client.post(
        "/api/register",
        json={
            "username": "alice",
            "password": "secret123",
            "email": "alice@example.com",
        },
    )
    db.execute(
        "UPDATE users SET password = ? WHERE username = 'alice'",
        (legacy_hash_password("secret123"),),
    )
    db.commit()

    assert (
        client.post(
            "/api/login", json={"username": "alice", "password": "secret123"}
        ).status_code
        == 200
    )
    row = db.execute("SELECT password FROM users WHERE username = 'alice'").fetchone()
    assert row["password"].startswith(("scrypt:", "pbkdf2:"))


def test_reset_token_flow_and_session_invalidation(client, monkeypatch):
    client.post(
        "/api/register",
        json={
            "username": "alice",
            "password": "secret123",
            "email": "alice@example.com",
        },
    )
    old_client = app_module.app.test_client()
    old_client.post("/api/login", json={"username": "alice", "password": "secret123"})

    captured = []
    monkeypatch.setattr(
        app_module, "send_email", lambda to, subject, html: captured.append(html) or True
    )
    assert (
        client.post(
            "/api/forgot-password", json={"email": "alice@example.com"}
        ).status_code
        == 200
    )
    assert captured
    token = re.search(r"/reset-password/([A-Za-z0-9_\-]+)", captured[-1]).group(1)

    assert client.get(f"/reset-password/{token}").status_code == 200
    assert (
        client.post(
            "/api/reset-password",
            json={"token": token, "new_password": "newpass123"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/reset-password",
            json={"token": token, "new_password": "another123"},
        ).status_code
        == 400
    )
    assert old_client.get("/api/me").status_code == 401
    assert (
        client.post(
            "/api/login", json={"username": "alice", "password": "secret123"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/login", json={"username": "alice", "password": "newpass123"}
        ).status_code
        == 200
    )


def test_reset_token_is_stored_hashed(client, db, monkeypatch):
    client.post(
        "/api/register",
        json={
            "username": "alice",
            "password": "secret123",
            "email": "alice@example.com",
        },
    )
    captured = []
    monkeypatch.setattr(
        app_module, "send_email", lambda to, subject, html: captured.append(html) or True
    )
    client.post("/api/forgot-password", json={"email": "alice@example.com"})
    token = re.search(r"/reset-password/([A-Za-z0-9_\-]+)", captured[-1]).group(1)

    row = db.execute("SELECT token_hash FROM password_reset_tokens").fetchone()
    assert token not in row["token_hash"]
    assert len(row["token_hash"]) == 64


def test_forgot_password_rate_limit(client, monkeypatch):
    client.post(
        "/api/register",
        json={
            "username": "alice",
            "password": "secret123",
            "email": "alice@example.com",
        },
    )
    captured = []
    monkeypatch.setattr(
        app_module, "send_email", lambda to, subject, html: captured.append(html) or True
    )
    for _ in range(6):
        client.post("/api/forgot-password", json={"email": "alice@example.com"})
    assert len(captured) <= 5


def test_change_password(client):
    client.post(
        "/api/register",
        json={
            "username": "alice",
            "password": "secret123",
            "email": "alice@example.com",
        },
    )
    client.post("/api/login", json={"username": "alice", "password": "secret123"})

    assert (
        client.put(
            "/api/me/password",
            json={"current_password": "bad", "new_password": "newpass123"},
        ).status_code
        == 400
    )
    assert (
        client.put(
            "/api/me/password",
            json={"current_password": "secret123", "new_password": "newpass123"},
        ).status_code
        == 200
    )
    assert client.get("/api/me").status_code == 401
    assert (
        client.post(
            "/api/login", json={"username": "alice", "password": "newpass123"}
        ).status_code
        == 200
    )


def test_change_email_and_logout_all(client):
    client.post(
        "/api/register",
        json={
            "username": "alice",
            "password": "secret123",
            "email": "alice@example.com",
        },
    )
    client.post("/api/login", json={"username": "alice", "password": "secret123"})

    assert (
        client.put(
            "/api/me/email",
            json={"email": "new@example.com", "current_password": "bad"},
        ).status_code
        == 400
    )
    response = client.put(
        "/api/me/email",
        json={"email": "new@example.com", "current_password": "secret123"},
    )
    assert response.status_code == 200
    assert client.get("/api/me").get_json()["email"] == "new@example.com"

    assert client.post("/api/me/logout-all").status_code == 200
    assert client.get("/api/me").status_code == 401
