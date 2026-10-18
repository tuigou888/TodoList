"""每日提醒与邮件模板测试。"""

import datetime as dt

import app as app_module
from todo_app.mailer import build_reminder_email


def _set_reminder_now(conn, enabled=1):
    now = dt.datetime.now()
    minutes = now.hour * 60 + now.minute
    conn.execute(
        "UPDATE users SET reminder_time = ?, reminder_enabled = ?, last_reminded_on = NULL",
        (minutes, enabled),
    )
    conn.commit()


def test_scheduled_reminder_sends_once_per_day(auth_client, monkeypatch):
    auth_client.post("/api/todos", json={"title": "任务"})
    captured = []
    monkeypatch.setattr(
        app_module, "send_email", lambda to, subject, html: captured.append(html) or True
    )
    monkeypatch.setattr(app_module.Config, "MAIL_ENABLED", True)

    conn = app_module.get_db_connection()
    _set_reminder_now(conn)
    conn.close()

    assert app_module.send_scheduled_reminders() == 1
    assert app_module.send_scheduled_reminders() == 0
    assert len(captured) == 1


def test_scheduled_reminder_respects_switch(auth_client, monkeypatch):
    auth_client.post("/api/todos", json={"title": "任务"})
    captured = []
    monkeypatch.setattr(
        app_module, "send_email", lambda to, subject, html: captured.append(html) or True
    )
    monkeypatch.setattr(app_module.Config, "MAIL_ENABLED", True)

    conn = app_module.get_db_connection()
    _set_reminder_now(conn, enabled=0)
    conn.close()

    assert app_module.send_scheduled_reminders() == 0
    assert captured == []


def test_manual_reminder_is_rate_limited(auth_client, monkeypatch):
    auth_client.post("/api/todos", json={"title": "任务"})
    captured = []
    monkeypatch.setattr(
        app_module, "send_email", lambda to, subject, html: captured.append(html) or True
    )
    monkeypatch.setattr(app_module.Config, "MAIL_ENABLED", True)

    assert auth_client.post("/api/send-reminder-now").status_code == 200
    assert auth_client.post("/api/send-reminder-now").status_code == 429
    assert len(captured) == 1


def test_reminder_email_escapes_user_input():
    user = {"username": "<b>u</b>", "reminder_time": 540, "email": "u@example.com"}
    todo = {
        "title": "<img src=x onerror=alert(1)>",
        "created_at": "2026-01-01 10:00:00",
    }
    html = build_reminder_email(user, [todo], dt.datetime(2026, 1, 1, 10, 0))
    assert "&lt;img" in html
    assert "<img src=x" not in html
    assert "&lt;b&gt;" in html
