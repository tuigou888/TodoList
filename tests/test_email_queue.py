"""邮件 outbox 队列、重试与管理接口测试。"""

import app as app_module
from todo_app import outbox


def test_enqueue_and_process_success(client, monkeypatch):
    monkeypatch.setattr(app_module.Config, "MAIL_ENABLED", True)
    sent = []
    monkeypatch.setattr(
        outbox,
        "send_email",
        lambda to, subject, html: sent.append(to) or True,
    )

    assert (
        app_module.enqueue_email("to@example.com", "主题", "<p>hi</p>") is True
    )

    conn = app_module.get_db_connection()
    row = conn.execute(
        "SELECT status, attempts FROM email_outbox"
    ).fetchone()
    conn.close()
    assert row["status"] == "pending"
    assert row["attempts"] == 0

    assert app_module.process_email_outbox() == 1

    conn = app_module.get_db_connection()
    row = conn.execute(
        "SELECT status, attempts, sent_at FROM email_outbox"
    ).fetchone()
    conn.close()
    assert row["status"] == "sent"
    assert row["attempts"] == 1
    assert row["sent_at"]
    assert sent == ["to@example.com"]


def test_failed_email_retries_then_marks_failed(client, monkeypatch):
    monkeypatch.setattr(app_module.Config, "MAIL_ENABLED", True)
    monkeypatch.setattr(outbox, "send_email", lambda *args: False)

    app_module.enqueue_email("to@example.com", "主题", "<p>hi</p>")

    for _ in range(app_module.EMAIL_MAX_ATTEMPTS):
        conn = app_module.get_db_connection()
        conn.execute(
            "UPDATE email_outbox SET next_attempt_at = ?", (app_module.now_string(),)
        )
        conn.commit()
        conn.close()
        app_module.process_email_outbox()

    conn = app_module.get_db_connection()
    row = conn.execute(
        "SELECT status, attempts, last_error FROM email_outbox"
    ).fetchone()
    conn.close()
    assert row["status"] == "failed"
    assert row["attempts"] == app_module.EMAIL_MAX_ATTEMPTS
    assert row["last_error"]


def test_processing_skipped_when_mail_disabled(client, monkeypatch):
    monkeypatch.setattr(app_module.Config, "MAIL_ENABLED", False)
    app_module.enqueue_email("to@example.com", "主题", "<p>hi</p>")
    assert app_module.process_email_outbox() == 0


def test_forgot_password_uses_outbox(client, db):
    client.post(
        "/api/register",
        json={
            "username": "alice",
            "password": "secret123",
            "email": "alice@example.com",
        },
    )
    client.post("/api/forgot-password", json={"email": "alice@example.com"})

    row = db.execute(
        "SELECT status, to_email FROM email_outbox ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row["status"] == "pending"
    assert row["to_email"] == "alice@example.com"


def test_admin_email_list_and_retry(admin_client):
    conn = app_module.get_db_connection()
    now = app_module.now_string()
    cursor = conn.execute(
        """
        INSERT INTO email_outbox
            (user_id, to_email, subject, html, status, attempts, next_attempt_at, created_at, last_error)
        VALUES (NULL, ?, ?, ?, 'failed', 3, ?, ?, ?)
        """,
        ("to@example.com", "主题", "<p>x</p>", now, now, "SMTP 失败"),
    )
    email_id = cursor.lastrowid
    conn.commit()
    conn.close()

    response = admin_client.get("/api/admin/emails?status=failed")
    assert response.status_code == 200
    assert any(item["id"] == email_id for item in response.get_json())

    assert (
        admin_client.post(f"/api/admin/emails/{email_id}/retry").status_code == 200
    )
    pending = admin_client.get("/api/admin/emails?status=pending").get_json()
    assert any(item["id"] == email_id for item in pending)

    stats = admin_client.get("/api/admin/stats").get_json()
    assert "emails_pending" in stats
    assert "emails_failed" in stats


def test_delete_user_removes_outbox(admin_client):
    response = admin_client.post(
        "/api/admin/users",
        json={
            "username": "bob",
            "password": "secret123",
            "email": "bob@example.com",
        },
    )
    bob_id = response.get_json()["id"]

    conn = app_module.get_db_connection()
    conn.execute(
        """
        INSERT INTO email_outbox
            (user_id, to_email, subject, html, status, attempts, next_attempt_at, created_at)
        VALUES (?, ?, ?, ?, 'pending', 0, ?, ?)
        """,
        (bob_id, "bob@example.com", "主题", "<p>x</p>", app_module.now_string(), app_module.now_string()),
    )
    conn.commit()
    conn.close()

    assert admin_client.delete(f"/api/admin/users/{bob_id}").status_code == 200

    conn = app_module.get_db_connection()
    remaining = conn.execute(
        "SELECT COUNT(*) FROM email_outbox WHERE user_id = ?", (bob_id,)
    ).fetchone()[0]
    conn.close()
    assert remaining == 0
