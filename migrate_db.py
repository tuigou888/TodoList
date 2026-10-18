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

DB_NAME = "todos.db"


def get_db_connection():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


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
                reminder_time INTEGER DEFAULT 540,
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
                user_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """
        )

        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]

        if "is_admin" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
            print("✓ 添加 is_admin 字段")

        if "last_login_at" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP")
            print("✓ 添加 last_login_at 字段")

        if "reminder_time" not in columns:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN reminder_time INTEGER DEFAULT 540"
            )
            print("✓ 添加 reminder_time 字段")

        cursor.execute("PRAGMA table_info(todos)")
        todo_columns = [column[1] for column in cursor.fetchall()]

        if "user_id" not in todo_columns:
            cursor.execute("ALTER TABLE todos ADD COLUMN user_id INTEGER")
            print("✓ 添加 user_id 字段")

        if "created_date" not in todo_columns:
            cursor.execute("ALTER TABLE todos ADD COLUMN created_date DATE")
            print("✓ 添加 created_date 字段")

        # 查询索引（与 app.init_db 保持一致）
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_todos_user_id ON todos(user_id)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_todos_user_completed ON todos(user_id, completed)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_todos_user_date ON todos(user_id, created_date)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")

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
