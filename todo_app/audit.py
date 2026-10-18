"""管理员操作审计日志。"""

from datetime import datetime


def log_audit(conn, actor_id, action, target_type=None, target_id=None, detail=None):
    """记录关键操作，便于管理员追溯。"""
    conn.execute(
        "INSERT INTO audit_logs (actor_id, action, target_type, target_id, detail, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            actor_id,
            action,
            target_type,
            target_id,
            detail,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
