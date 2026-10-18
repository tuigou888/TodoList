"""数据库连接、初始化与时间工具。"""

import logging
import os
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

DB_NAME = os.environ.get("DB_NAME", "todos.db")


def get_db_connection():
    """
    获取数据库连接
    返回一个支持字典式访问的 SQLite 连接对象
    """
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    # 每个连接都必须开启外键约束（SQLite 默认关闭）
    conn.execute("PRAGMA foreign_keys = ON")
    # 并发写入时等待锁释放，而不是立刻抛 database is locked
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def ensure_column(conn, table, column, definition):
    """
    为已有表补充缺失字段（幂等）。
    table/column 均来自代码常量，不存在注入风险。
    """
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        logger.info("数据库迁移：%s 表新增字段 %s", table, column)


def init_db():
    """
    初始化数据库
    创建用户表和待办事项表（如果不存在），并创建查询索引
    """
    conn = get_db_connection()

    # WAL 模式允许读写并发，避免多 worker 下频繁出现 database is locked
    conn.execute("PRAGMA journal_mode = WAL")

    conn.execute(
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
            api_token_hash TEXT,
            api_token_created_at TIMESTAMP,
            review_enabled INTEGER DEFAULT 0,
            review_time INTEGER DEFAULT 1200,
            last_review_on DATE,
            last_weekly_review_on DATE,
            ics_token TEXT,
            created_at TIMESTAMP DEFAULT (DATETIME('now', 'localtime')),
            last_login_at TIMESTAMP
        )
    """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed INTEGER DEFAULT 0,
            created_date DATE,
            created_at TIMESTAMP,
            due_date DATE,
            due_time TEXT,
            priority INTEGER DEFAULT 2,
            tags TEXT,
            context TEXT,
            is_mit INTEGER DEFAULT 0,
            mit_date DATE,
            completed_at TIMESTAMP,
            updated_at TIMESTAMP,
            deleted_at TIMESTAMP,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """
    )
    conn.execute(
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

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS password_reset_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            requested_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """
    )

    conn.execute(
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

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            ip TEXT,
            attempted_at TIMESTAMP NOT NULL,
            success INTEGER NOT NULL DEFAULT 0
        )
    """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS email_outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            to_email TEXT NOT NULL,
            subject TEXT NOT NULL,
            html TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            next_attempt_at TIMESTAMP NOT NULL,
            last_error TEXT,
            created_at TIMESTAMP NOT NULL,
            sent_at TIMESTAMP
        )
    """
    )

    # 权限系统表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            resource TEXT,
            action TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS role_permissions (
            role_id INTEGER NOT NULL,
            permission_id INTEGER NOT NULL,
            PRIMARY KEY (role_id, permission_id),
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
            FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS permission_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            permission TEXT NOT NULL,
            action TEXT,
            resource TEXT,
            success INTEGER DEFAULT 1,
            ip_address TEXT,
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_perm_logs_user ON permission_logs(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_perm_logs_created ON permission_logs(created_at DESC)")

    # 迁移现有用户到角色系统
    ensure_column(conn, "users", "role_id", "INTEGER DEFAULT 1")
    ensure_column(conn, "users", "custom_permissions", "TEXT")
    conn.execute("UPDATE users SET role_id = 1 WHERE is_admin = 1 AND role_id IS NULL")
    conn.execute("UPDATE users SET role_id = 3 WHERE is_admin = 0 AND role_id IS NULL")

    # 老数据库补字段（幂等）
    ensure_column(conn, "users", "is_admin", "INTEGER DEFAULT 0")
    ensure_column(conn, "users", "is_active", "INTEGER DEFAULT 1")
    ensure_column(conn, "users", "reminder_time", "INTEGER DEFAULT 540")
    ensure_column(conn, "users", "last_login_at", "TIMESTAMP")
    ensure_column(conn, "users", "reminder_enabled", "INTEGER DEFAULT 1")
    ensure_column(conn, "users", "last_reminded_on", "DATE")
    ensure_column(conn, "users", "last_manual_reminder_at", "TIMESTAMP")
    ensure_column(conn, "users", "session_version", "INTEGER DEFAULT 0")
    ensure_column(conn, "users", "api_token_hash", "TEXT")
    ensure_column(conn, "users", "api_token_created_at", "TIMESTAMP")
    ensure_column(conn, "users", "review_enabled", "INTEGER DEFAULT 0")
    ensure_column(conn, "users", "review_time", "INTEGER DEFAULT 1200")
    ensure_column(conn, "users", "last_review_on", "DATE")
    ensure_column(conn, "users", "last_weekly_review_on", "DATE")
    ensure_column(conn, "users", "ics_token", "TEXT")
    ensure_column(conn, "todos", "user_id", "INTEGER")
    ensure_column(conn, "todos", "created_date", "DATE")
    ensure_column(conn, "todos", "due_date", "DATE")
    ensure_column(conn, "todos", "due_time", "TEXT")
    ensure_column(conn, "todos", "priority", "INTEGER DEFAULT 2")
    ensure_column(conn, "todos", "tags", "TEXT")
    ensure_column(conn, "todos", "context", "TEXT")
    ensure_column(conn, "todos", "is_mit", "INTEGER DEFAULT 0")
    ensure_column(conn, "todos", "mit_date", "DATE")
    ensure_column(conn, "todos", "completed_at", "TIMESTAMP")
    ensure_column(conn, "todos", "updated_at", "TIMESTAMP")
    ensure_column(conn, "todos", "deleted_at", "TIMESTAMP")
    ensure_column(conn, "todos", "context", "TEXT")
    ensure_column(conn, "todos", "is_mit", "INTEGER DEFAULT 0")
    ensure_column(conn, "todos", "mit_date", "DATE")

    # 初始化权限数据
    from todo_app.permissions import init_permissions_table
    init_permissions_table(conn)

    # 常用查询索引：按用户、完成状态、日期检索
    conn.execute("CREATE INDEX IF NOT EXISTS idx_todos_user_id ON todos(user_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_todos_user_completed ON todos(user_id, completed)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_todos_user_date ON todos(user_id, created_date)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_prt_user_id ON password_reset_tokens(user_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_prt_expires ON password_reset_tokens(expires_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_prr_user_time ON password_reset_requests(user_id, requested_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_todos_user_due ON todos(user_id, due_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_todos_user_priority ON todos(user_id, priority)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_todos_user_deleted ON todos(user_id, deleted_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_todos_user_mit ON todos(user_id, is_mit, mit_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_login_attempts_user ON login_attempts(username, attempted_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_email_outbox_status ON email_outbox(status, next_attempt_at)"
    )

    conn.commit()
    conn.close()


def now_string(moment=None):
    """统一的时间字符串格式（本地时间，精确到秒）"""
    return (moment or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")

