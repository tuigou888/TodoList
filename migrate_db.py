import sqlite3
import hashlib
import sys

DB_NAME = "todos.db"


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def migrate_database():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
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

        conn.commit()
        print("✓ 数据库迁移完成")

        cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
        admin_count = cursor.fetchone()[0]

        if admin_count == 0:
            print("\n创建默认管理员账户...")
            admin_username = "admin"
            admin_password = "admin123"
            admin_email = "admin@example.com"

            hashed_password = hash_password(admin_password)
            cursor.execute(
                "INSERT INTO users (username, password, email, is_admin) VALUES (?, ?, ?, 1)",
                (admin_username, hashed_password, admin_email),
            )
            conn.commit()
            print(f"✓ 管理员账户创建成功: {admin_username}")
            print(f"  用户名: {admin_username}")
            print(f"  密码: {admin_password}")
        else:
            print(f"\n✓ 已存在 {admin_count} 个管理员账户")

    except Exception as e:
        conn.rollback()
        print(f"✗ 迁移失败: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_database()
