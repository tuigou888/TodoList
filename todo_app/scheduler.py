"""每日提醒、手动提醒与邮件队列调度。"""

import logging
import threading
import time
from datetime import datetime, timedelta

from config import Config
from todo_app.db import get_db_connection, now_string
from todo_app.mailer import build_reminder_email, send_email
from todo_app.outbox import enqueue_email, process_email_outbox

logger = logging.getLogger(__name__)

REMINDER_SCHEDULER_STARTED = False
MANUAL_REMINDER_INTERVAL_SECONDS = 60
LAST_DELETED_PURGE_DATE = None
def purge_expired_deleted(days=30):
    """每天清理一次回收站中超过保留期的待办"""
    global LAST_DELETED_PURGE_DATE
    today = datetime.now().strftime("%Y-%m-%d")
    if LAST_DELETED_PURGE_DATE == today:
        return 0
    LAST_DELETED_PURGE_DATE = today

    cutoff = now_string(datetime.now() - timedelta(days=days))
    conn = get_db_connection()
    cursor = conn.execute(
        "DELETE FROM todos WHERE deleted_at IS NOT NULL AND deleted_at < ?",
        (cutoff,),
    )
    conn.commit()
    conn.close()
    if cursor.rowcount:
        logger.info("已清理 %s 条过期回收站待办", cursor.rowcount)
    return cursor.rowcount


def get_unfinished_todos(conn, user_id):
    return conn.execute(
        "SELECT * FROM todos WHERE user_id = ? AND completed = 0 AND deleted_at IS NULL ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()


def send_reminder_for_user(conn, user, now=None):
    """给单个用户发送未完成待办摘要，返回是否成功"""
    if not user["email"]:
        return False
    todos = get_unfinished_todos(conn, user["id"])
    if not todos:
        return False
    now = now or datetime.now()
    html_content = build_reminder_email(user, todos, now)
    return enqueue_email(
        user["email"],
        f"待办事项提醒 - {now.strftime('%Y-%m-%d')}",
        html_content,
        user_id=user["id"],
    )


def send_scheduled_reminders():
    """
    按用户设置的 reminder_time 发送每日提醒。
    通过 last_reminded_on 原子占位，保证每个用户每天最多一封（多进程安全）。
    """
    purge_expired_deleted()

    if not Config.MAIL_ENABLED:
        return 0

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    current_minutes = now.hour * 60 + now.minute

    conn = get_db_connection()
    sent = 0
    try:
        candidates = conn.execute(
            """
            SELECT * FROM users
            WHERE email IS NOT NULL AND email != ''
              AND COALESCE(reminder_enabled, 1) = 1
              AND COALESCE(last_reminded_on, '') != ?
              AND CAST(COALESCE(reminder_time, 540) AS INTEGER) <= ?
            """,
            (today, current_minutes),
        ).fetchall()

        for user in candidates:
            # 先原子占位再发送，避免多进程或重启导致重复邮件
            cursor = conn.execute(
                "UPDATE users SET last_reminded_on = ? WHERE id = ? AND COALESCE(last_reminded_on, '') != ?",
                (today, user["id"], today),
            )
            conn.commit()
            if cursor.rowcount != 1:
                continue

            try:
                if send_reminder_for_user(conn, user, now):
                    sent += 1
            except Exception:
                logger.exception("发送提醒失败（user_id=%s）", user["id"])
    finally:
        conn.close()

    if sent:
        logger.info("已发送 %s 封每日提醒", sent)
    return sent


def send_manual_reminder(user):
    """
    手动立即发送一次提醒，带最小间隔限制。
    返回 (是否成功, 提示信息, HTTP 状态码)
    """
    if not Config.MAIL_ENABLED:
        return False, "邮件服务未启用", 400
    if not user["email"]:
        return False, "用户未设置邮箱", 400

    now = datetime.now()
    last = user["last_manual_reminder_at"]
    if last:
        try:
            last_dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
            if (now - last_dt).total_seconds() < MANUAL_REMINDER_INTERVAL_SECONDS:
                return False, "操作过于频繁，请稍后再试", 429
        except ValueError:
            pass

    conn = get_db_connection()
    try:
        todos = get_unfinished_todos(conn, user["id"])
        if not todos:
            return False, "没有未完成的待办事项", 200

        html_content = build_reminder_email(user, todos, now)
        if not send_email(
            user["email"],
            f"待办事项提醒 - {now.strftime('%Y-%m-%d')}",
            html_content,
        ):
            return False, "邮件发送失败，请稍后重试", 500

        conn.execute(
            "UPDATE users SET last_manual_reminder_at = ? WHERE id = ?",
            (now_string(now), user["id"]),
        )
        conn.commit()
    finally:
        conn.close()

    return True, "提醒邮件已发送", 200


def start_reminder_scheduler():
    """
    启动每日提醒调度器：每分钟检查一次，按用户的 reminder_time 发送。
    """
    global REMINDER_SCHEDULER_STARTED
    if REMINDER_SCHEDULER_STARTED:
        return

    REMINDER_SCHEDULER_STARTED = True

    def scheduler():
        logger.info("每日提醒调度器已启动（每分钟检查一次）")
        while True:
            try:
                send_scheduled_reminders()
            except Exception:
                logger.exception("提醒任务执行失败")

            try:
                process_email_outbox()
            except Exception:
                logger.exception("邮件队列处理失败")

            # 对齐到下一分钟，避免长期运行产生漂移
            time.sleep(max(60 - datetime.now().second, 1))

    thread = threading.Thread(target=scheduler, daemon=True)
    thread.start()
    logger.info("邮件提醒定时任务已启动")

