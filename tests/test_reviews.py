"""每日/每周回顾邮件与设置测试。"""

import datetime as dt

import app as app_module
from todo_app import reviews
from todo_app.mailer import build_daily_review_email


def _set_review_now(conn, enabled=1):
    now = dt.datetime.now()
    minutes = now.hour * 60 + now.minute
    conn.execute(
        "UPDATE users SET review_enabled = ?, review_time = ?, last_review_on = NULL WHERE username = 'alice'",
        (enabled, minutes),
    )
    conn.commit()


def test_daily_review_sends_once(auth_client, monkeypatch):
    auth_client.post("/api/todos", json={"title": "任务"})
    queued = []
    monkeypatch.setattr(
        reviews,
        "enqueue_email",
        lambda to, subject, html, user_id=None: queued.append(subject) or True,
    )
    monkeypatch.setattr(app_module.Config, "MAIL_ENABLED", True)

    conn = app_module.get_db_connection()
    _set_review_now(conn)
    conn.close()

    assert app_module.send_daily_reviews() == 1
    assert app_module.send_daily_reviews() == 0
    assert len(queued) == 1


def test_daily_review_respects_switch(auth_client, monkeypatch):
    queued = []
    monkeypatch.setattr(
        reviews,
        "enqueue_email",
        lambda to, subject, html, user_id=None: queued.append(subject) or True,
    )
    monkeypatch.setattr(app_module.Config, "MAIL_ENABLED", True)

    conn = app_module.get_db_connection()
    _set_review_now(conn, enabled=0)
    conn.close()

    assert app_module.send_daily_reviews() == 0
    assert queued == []


def test_review_settings_api(auth_client):
    response = auth_client.put(
        "/api/me/review",
        json={"review_enabled": True, "review_hour": 21, "review_minute": 30},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["review_enabled"] is True
    assert data["review_hour"] == 21
    assert data["review_minute"] == 30

    me = auth_client.get("/api/me").get_json()
    assert me["review_enabled"] is True
    assert me["review_hour"] == 21
    assert me["review_minute"] == 30

    assert (
        auth_client.put(
            "/api/me/review", json={"review_hour": 99}
        ).status_code
        == 400
    )


def test_send_review_now(auth_client):
    auth_client.post("/api/todos", json={"title": "任务"})
    response = auth_client.post("/api/me/review/send")
    assert response.status_code == 200

    conn = app_module.get_db_connection()
    count = conn.execute("SELECT COUNT(*) FROM email_outbox").fetchone()[0]
    conn.close()
    assert count == 1


def test_collect_review_stats(auth_client):
    todo_id = auth_client.post(
        "/api/todos", json={"title": "逾期任务", "due_date": "2000-01-01"}
    ).get_json()["id"]
    auth_client.post("/api/todos", json={"title": "普通任务"})
    auth_client.put(f"/api/todos/{todo_id}", json={"completed": True})

    conn = app_module.get_db_connection()
    stats = reviews.collect_review_stats(
        conn, 1, dt.datetime.now()
    )
    conn.close()

    assert stats["completed"] == 1
    assert stats["pending"] == 1
    assert stats["oldest_title"] is not None


def test_review_email_escapes_user_input():
    user = {"username": "<b>alice</b>", "email": "a@example.com"}
    stats = {
        "completed_today": 1,
        "pending": 1,
        "overdue": 0,
        "mit_total": 2,
        "mit_completed": 1,
        "week_completed": 3,
        "week_created": 4,
        "completion_rate": 50.0,
        "oldest_title": "<script>alert(1)</script>",
        "oldest_created_at": "2026-01-01 10:00:00",
    }
    todos = [
        {"title": "<img src=x onerror=alert(1)>", "priority": 3, "due_date": None}
    ]
    html = build_daily_review_email(user, stats, todos, dt.datetime(2026, 1, 1, 20, 0))
    assert "&lt;b&gt;alice&lt;/b&gt;" in html
    assert "&lt;img src=x" in html
    assert "<img src=x" not in html
