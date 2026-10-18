"""密码重置令牌的生成、校验与消耗。"""

import secrets
from datetime import datetime, timedelta

from todo_app.db import get_db_connection, now_string
from todo_app.security import hash_password, hash_reset_token

RESET_TOKEN_TTL_SECONDS = 3600
RESET_TOKEN_REQUEST_WINDOW_SECONDS = 300
RESET_TOKEN_MAX_REQUESTS = 5
RESET_TOKEN_MAX_ACTIVE = 3
def cleanup_reset_tokens(conn, now=None):
    """清理过期或已使用的令牌"""
    conn.execute(
        "DELETE FROM password_reset_tokens WHERE expires_at < ? OR used_at IS NOT NULL",
        (now_string(now),),
    )


def reset_request_allowed(user_id):
    """同一用户短时间内申请重置的次数限制，避免邮件轰炸"""
    cutoff = now_string(
        datetime.now() - timedelta(seconds=RESET_TOKEN_REQUEST_WINDOW_SECONDS)
    )
    conn = get_db_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM password_reset_requests WHERE user_id = ? AND requested_at >= ?",
        (user_id, cutoff),
    ).fetchone()[0]
    conn.close()
    return count < RESET_TOKEN_MAX_REQUESTS


def generate_reset_token(user_id):
    """
    生成密码重置令牌并写入数据库。
    :param user_id: 用户ID
    :return: 明文令牌（只出现在邮件链接中）
    """
    token = secrets.token_urlsafe(32)
    token_hash = hash_reset_token(token)
    now = datetime.now()
    expires = now + timedelta(seconds=RESET_TOKEN_TTL_SECONDS)

    conn = get_db_connection()
    try:
        cleanup_reset_tokens(conn, now)

        # 记录请求流水用于频率限制，并清理一天前的旧记录
        conn.execute(
            "DELETE FROM password_reset_requests WHERE requested_at < ?",
            (now_string(now - timedelta(days=1)),),
        )
        conn.execute(
            "INSERT INTO password_reset_requests (user_id, requested_at) VALUES (?, ?)",
            (user_id, now_string(now)),
        )

        # 每个用户只保留最新的若干个有效令牌
        active = conn.execute(
            "SELECT id FROM password_reset_tokens WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        for row in active[RESET_TOKEN_MAX_ACTIVE - 1 :]:
            conn.execute(
                "DELETE FROM password_reset_tokens WHERE id = ?", (row["id"],)
            )

        conn.execute(
            "INSERT INTO password_reset_tokens (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token_hash, user_id, now_string(now), now_string(expires)),
        )
        conn.commit()
    finally:
        conn.close()

    return token


def get_reset_token(token):
    """查询有效令牌，返回 (数据行, 错误信息)"""
    if not isinstance(token, str) or not token.strip():
        return None, "链接无效或已过期"

    token_hash = hash_reset_token(token.strip())
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM password_reset_tokens WHERE token_hash = ?", (token_hash,)
    ).fetchone()
    conn.close()

    if not row or row["used_at"]:
        return None, "链接无效或已过期"
    if row["expires_at"] < now_string():
        return None, "链接已过期"
    return row, None


def reset_password_with_token(token, new_password):
    """
    原子地消耗令牌并修改密码，同时递增 session_version 使旧会话失效。
    返回 user_id，令牌无效时返回 None。
    """
    token_hash = hash_reset_token(token.strip())
    now = now_string()

    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM password_reset_tokens WHERE token_hash = ?", (token_hash,)
        ).fetchone()
        if not row or row["used_at"] or row["expires_at"] < now:
            return None

        cursor = conn.execute(
            "UPDATE password_reset_tokens SET used_at = ? WHERE id = ? AND used_at IS NULL",
            (now, row["id"]),
        )
        if cursor.rowcount != 1:
            return None

        conn.execute(
            "UPDATE users SET password = ?, session_version = session_version + 1 WHERE id = ?",
            (hash_password(new_password), row["user_id"]),
        )
        conn.commit()
    finally:
        conn.close()

    return row["user_id"]

