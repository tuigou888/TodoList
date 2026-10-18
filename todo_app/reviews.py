"""每日/每周回顾邮件。"""

import logging
from datetime import datetime, timedelta

from config import Config
from todo_app.db import get_db_connection
from todo_app.mailer import build_daily_review_email, build_weekly_review_email
from todo_app.outbox import enqueue_email

logger = logging.getLogger(__name__)


def _day_start(day):
    return day.strftime("%Y-%m-%d") + " 00:00:00"


def _week_start(day):
    return (day - timedelta(days=day.weekday())).strftime("%Y-%m-%d")


def collect_review_stats(conn, user_id, today):
    """汇总回顾邮件所需的统计。"""
    today_str = today.strftime("%Y-%m-%d")
    week_start = _week_start(today)

    row = conn.execute(
        """
        SELECT
          SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END) AS pending,
          SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS completed,
          SUM(CASE WHEN completed = 0 AND due_date IS NOT NULL AND due_date < ? THEN 1 ELSE 0 END) AS overdue,
          SUM(CASE WHEN created_date = ? THEN 1 ELSE 0 END) AS created_today,
          SUM(CASE WHEN completed_at >= ? THEN 1 ELSE 0 END) AS completed_today,
          SUM(CASE WHEN is_mit = 1 AND mit_date = ? THEN 1 ELSE 0 END) AS mit_total,
          SUM(CASE WHEN is_mit = 1 AND mit_date = ? AND completed = 1 THEN 1 ELSE 0 END) AS mit_completed,
          SUM(CASE WHEN completed_at >= ? THEN 1 ELSE 0 END) AS week_completed,
          SUM(CASE WHEN created_date >= ? THEN 1 ELSE 0 END) AS week_created
        FROM todos WHERE user_id = ? AND deleted_at IS NULL
        """,
        (
            today_str,
            today_str,
            _day_start(today),
            today_str,
            today_str,
            _day_start(today),
            week_start,
            user_id,
        ),
    ).fetchone()

    stats = {key: (row[key] or 0) for key in row.keys()}
    handled = stats["completed"] + stats["pending"]
    stats["completion_rate"] = (
        round(stats["completed"] * 100 / handled, 1) if handled else 0.0
    )

    oldest = conn.execute(
        """
        SELECT title, created_at FROM todos
        WHERE user_id = ? AND completed = 0 AND deleted_at IS NULL
        ORDER BY created_at ASC LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    stats["oldest_title"] = oldest["title"] if oldest else None
    stats["oldest_created_at"] = oldest["created_at"] if oldest else None
    return stats


def _pending_todos(conn, user_id, limit=10):
    return conn.execute(
        """
        SELECT * FROM todos
        WHERE user_id = ? AND completed = 0 AND deleted_at IS NULL
        ORDER BY priority DESC,
                 CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
                 due_date ASC,
                 created_at ASC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()


def send_daily_reviews():
    """按用户设定时间发送每日回顾，每天最多一封。"""
    if not Config.MAIL_ENABLED:
        return 0

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    current_minutes = now.hour * 60 + now.minute

    conn = get_db_connection()
    sent = 0
    try:
        users = conn.execute(
            """
            SELECT * FROM users
            WHERE email IS NOT NULL AND email != ''
              AND COALESCE(review_enabled, 0) = 1
              AND COALESCE(review_time, 1200) <= ?
              AND COALESCE(last_review_on, '') != ?
            """,
            (current_minutes, today),
        ).fetchall()

        for user in users:
            cursor = conn.execute(
                "UPDATE users SET last_review_on = ? WHERE id = ? AND COALESCE(last_review_on, '') != ?",
                (today, user["id"], today),
            )
            conn.commit()
            if cursor.rowcount != 1:
                continue

            stats = collect_review_stats(conn, user["id"], now)
            todos = _pending_todos(conn, user["id"])
            html = build_daily_review_email(user, stats, todos, now)
            if enqueue_email(
                user["email"], f"今日回顾 - {today}", html, user_id=user["id"]
            ):
                sent += 1
    finally:
        conn.close()

    if sent:
        logger.info("已发送 %s 封每日回顾", sent)
    return sent


def send_weekly_reviews():
    """每周一发送上周回顾，每周最多一封。"""
    if not Config.MAIL_ENABLED:
        return 0

    now = datetime.now()
    if now.weekday() != 0:
        return 0

    today = now.strftime("%Y-%m-%d")
    current_minutes = now.hour * 60 + now.minute

    conn = get_db_connection()
    sent = 0
    try:
        users = conn.execute(
            """
            SELECT * FROM users
            WHERE email IS NOT NULL AND email != ''
              AND COALESCE(review_enabled, 0) = 1
              AND COALESCE(review_time, 1200) <= ?
              AND COALESCE(last_weekly_review_on, '') != ?
            """,
            (current_minutes, today),
        ).fetchall()

        for user in users:
            cursor = conn.execute(
                "UPDATE users SET last_weekly_review_on = ? WHERE id = ? AND COALESCE(last_weekly_review_on, '') != ?",
                (today, user["id"], today),
            )
            conn.commit()
            if cursor.rowcount != 1:
                continue

            stats = collect_review_stats(conn, user["id"], now)
            todos = _pending_todos(conn, user["id"], limit=10)
            html = build_weekly_review_email(user, stats, todos, now)
            if enqueue_email(
                user["email"], f"每周回顾 - {today}", html, user_id=user["id"]
            ):
                sent += 1
    finally:
        conn.close()

    if sent:
        logger.info("已发送 %s 封每周回顾", sent)
    return sent
