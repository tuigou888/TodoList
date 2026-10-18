"""pytest 公共 fixture。"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789")
os.environ.setdefault("MAIL_ENABLED", "False")
os.environ.setdefault("CORS_ENABLED", "True")

import app as app_module  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(app_module, "DB_NAME", db_path)
    app_module.init_db()
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as test_client:
        yield test_client


@pytest.fixture()
def db(client):
    conn = app_module.get_db_connection()
    yield conn
    conn.close()


@pytest.fixture()
def auth_client(client):
    client.post(
        "/api/register",
        json={
            "username": "alice",
            "password": "secret123",
            "email": "alice@example.com",
        },
    )
    client.post("/api/login", json={"username": "alice", "password": "secret123"})
    return client


@pytest.fixture()
def admin_client(client):
    client.post(
        "/api/register",
        json={
            "username": "adminuser",
            "password": "secret123",
            "email": "admin@example.com",
        },
    )
    conn = app_module.get_db_connection()
    conn.execute("UPDATE users SET is_admin = 1 WHERE username = 'adminuser'")
    conn.commit()
    conn.close()
    client.post("/api/login", json={"username": "adminuser", "password": "secret123"})
    return client
