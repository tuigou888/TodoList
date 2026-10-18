"""邮件 outbox 队列：入队、清理与重试发送。"""

import logging
from datetime import datetime, timedelta

from config import Config
from todo_app.db import get_db_connection, now_string
from todo_app.mailer import send_email

logger = logging.getLogger(__name__)

EMAIL_MAX_ATTEMPTS = 3
EMAIL_RETRY_DELAYS = (60, 300, 900)
EMAIL_OUTBOX_RETENTION_DAYS = 30
def enqueue_email(to_email, subject, html_content, user_id=None):
    """把邮件写入发送队列，由调度器异步发送"""
    now = now_string()
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO email_outbox
                (user_id, to_email, subject, html, status, attempts, next_attempt_at, created_at)
            VALUES (?, ?, ?, ?, 'pending', 0, ?, ?)
            """,
            (user_id, to_email, subject, html_content, now, now),
        )
        conn.commit()
    except Exception:
        logger.exception("邮件入队失败")
        return False
    finally:
        conn.close()
    return True


def purge_email_outbox(days=EMAIL_OUTBOX_RETENTION_DAYS):
    """清理超过保留期的已结束邮件"""
    cutoff = now_string(datetime.now() - timedelta(days=days))
    deleted = 0
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM email_outbox WHERE status != 'pending' AND created_at < ?",
            (cutoff,),
        )
        deleted = cursor.rowcount
        conn.commit()
    finally:
        conn.close()
    return deleted


def process_email_outbox(limit=10):
    """
    处理到期的待发送邮件。
    成功标记 sent；失败按退避间隔重试，达到上限后标记 failed。
    """
    if not Config.MAIL_ENABLED:
        return 0

    purge_email_outbox()

    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM email_outbox WHERE status = 'pending' AND next_attempt_at <= ? ORDER BY id ASC LIMIT ?",
            (now_string(), limit),
        ).fetchall()
    finally:
        conn.close()

    processed = 0
    for row in rows:
        ok = send_email(row["to_email"], row["subject"], row["html"])
        conn = get_db_connection()
        try:
            if ok:
                conn.execute(
                    "UPDATE email_outbox SET status = 'sent', attempts = attempts + 1, sent_at = ?, last_error = NULL WHERE id = ?",
                    (now_string(), row["id"]),
                )
            else:
                attempts = row["attempts"] + 1
                if attempts >= EMAIL_MAX_ATTEMPTS:
                    conn.execute(
                        "UPDATE email_outbox SET status = 'failed', attempts = ?, last_error = ? WHERE id = ?",
                        (attempts, "发送失败，已达最大重试次数", row["id"]),
                    )
                else:
                    delay = EMAIL_RETRY_DELAYS[
                        min(attempts - 1, len(EMAIL_RETRY_DELAYS) - 1)
                    ]
                    next_at = now_string(datetime.now() + timedelta(seconds=delay))
                    conn.execute(
                        "UPDATE email_outbox SET attempts = ?, next_attempt_at = ?, last_error = ? WHERE id = ?",
                        (attempts, next_at, "SMTP 发送失败", row["id"]),
                    )
            conn.commit()
        finally:
            conn.close()
        processed += 1

    return processed

