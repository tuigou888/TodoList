"""
数据库迁移脚本
- 为旧数据库补充缺失字段
- 创建查询索引并启用 WAL
- 在没有任何管理员时创建一个管理员账户（密码来自 ADMIN_PASSWORD 或随机生成）
"""

import os
import secrets
import sqlite3

from werkzeug.security import generate_password_hash

DB_NAME = os.environ.get("DB_NAME", "todos.db")


def get_db_connection():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def ensure_column(cursor, table, column, definition):
    cursor.execute(f"PRAGMA table_info({table})")
    columns = {row[1] for row in cursor.fetchall()}
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        print(f"✓ 添加 {table}.{column} 字段")


def migrate_database():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA journal_mode = WAL")

        # 老数据库可能还没有表，先确保表存在
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT,
                is_admin INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                reminder_time INTEGER DEFAULT 540,
                reminder_enabled INTEGER DEFAULT 1,
                last_reminded_on DATE,
                last_manual_reminder_at TIMESTAMP,
                session_version INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT (DATETIME('now', 'localtime')),
                last_login_at TIMESTAMP
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                completed INTEGER DEFAULT 0,
                created_date DATE,
                created_at TIMESTAMP,
                due_date DATE,
                priority INTEGER DEFAULT 2,
                completed_at TIMESTAMP,
                updated_at TIMESTAMP,
                deleted_at TIMESTAMP,
                user_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS password_reset_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                requested_at TIMESTAMP NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_id INTEGER,
                action TEXT NOT NULL,
                target_type TEXT,
                target_id INTEGER,
                detail TEXT,
                created_at TIMESTAMP NOT NULL
            )
        """
        )

        # 历史字段迁移
        ensure_column(cursor, "users", "is_admin", "INTEGER DEFAULT 0")
        ensure_column(cursor, "users", "is_active", "INTEGER DEFAULT 1")
        ensure_column(cursor, "users", "last_login_at", "TIMESTAMP")
        ensure_column(cursor, "users", "reminder_time", "INTEGER DEFAULT 540")
        ensure_column(cursor, "users", "reminder_enabled", "INTEGER DEFAULT 1")
        ensure_column(cursor, "users", "last_reminded_on", "DATE")
        ensure_column(cursor, "users", "last_manual_reminder_at", "TIMESTAMP")
        ensure_column(cursor, "users", "session_version", "INTEGER DEFAULT 0")

        ensure_column(cursor, "todos", "user_id", "INTEGER")
        ensure_column(cursor, "todos", "created_date", "DATE")
        ensure_column(cursor, "todos", "due_date", "DATE")
        ensure_column(cursor, "todos", "priority", "INTEGER DEFAULT 2")
        ensure_column(cursor, "todos", "completed_at", "TIMESTAMP")
        ensure_column(cursor, "todos", "updated_at", "TIMESTAMP")
        ensure_column(cursor, "todos", "deleted_at", "TIMESTAMP")

        # 查询索引（与 app.init_db 保持一致）
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_todos_user_id ON todos(user_id)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_todos_user_completed ON todos(user_id, completed)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_todos_user_date ON todos(user_id, created_date)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_prt_user_id ON password_reset_tokens(user_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_prt_expires ON password_reset_tokens(expires_at)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_prr_user_time ON password_reset_requests(user_id, requested_at)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_todos_user_due ON todos(user_id, due_date)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_todos_user_priority ON todos(user_id, priority)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_todos_user_deleted ON todos(user_id, deleted_at)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at)"
        )

        conn.commit()
        print("✓ 数据库迁移完成")

        cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
        admin_count = cursor.fetchone()[0]

        if admin_count == 0:
            print("\n创建默认管理员账户...")
            admin_username = os.environ.get("ADMIN_USERNAME", "admin")
            admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
            admin_password = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(
                12
            )

            hashed_password = generate_password_hash(admin_password)
            cursor.execute(
                "INSERT INTO users (username, password, email, is_admin) VALUES (?, ?, ?, 1)",
                (admin_username, hashed_password, admin_email),
            )
            conn.commit()
            print(f"✓ 管理员账户创建成功: {admin_username}")
            print(f"  用户名: {admin_username}")
            if os.environ.get("ADMIN_PASSWORD"):
                print("  密码: 来自 ADMIN_PASSWORD 环境变量")
            else:
                print(f"  临时密码: {admin_password}")
                print("  请登录后立即修改密码")
        else:
            print(f"\n✓ 已存在 {admin_count} 个管理员账户")

    except Exception as e:
        conn.rollback()
        print(f"✗ 迁移失败: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_database()
