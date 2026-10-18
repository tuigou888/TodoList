"""
细粒度权限管理模块
实现 RBAC (Role-Based Access Control) + 操作权限控制
"""

import json
import logging
from functools import wraps
from flask import session, jsonify, g, request

logger = logging.getLogger(__name__)


def get_db_connection():
    """本地导入避免循环依赖"""
    from todo_app.db import get_db_connection as _get_db
    return _get_db()


# 预定义角色及其权限
ROLES = {
    "admin": {
        "name": "管理员",
        "permissions": [
            "users.view",
            "users.create",
            "users.edit",
            "users.delete",
            "todos.view_all",
            "todos.manage",
            "audit.view",
            "settings.manage",
            "emails.send",
        ],
    },
    "manager": {
        "name": "主管",
        "permissions": [
            "users.view",
            "todos.view_all",
            "todos.manage",
            "emails.send",
        ],
    },
    "user": {
        "name": "普通用户",
        "permissions": [
            "todos.manage",
            "settings.edit",
        ],
    },
}


def init_permissions_table(conn):
    """初始化权限相关表"""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            resource TEXT,
            action TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS role_permissions (
            role_id INTEGER NOT NULL,
            permission_id INTEGER NOT NULL,
            PRIMARY KEY (role_id, permission_id),
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
            FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
        )
    """
    )
    conn.execute(
        """
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
    """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_perm_logs_user ON permission_logs(user_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_perm_logs_created ON permission_logs(created_at DESC)"
    )

    # 插入预定义权限
    permissions_to_insert = [
        ("users.view", "查看用户列表", "user", "read"),
        ("users.create", "创建用户", "user", "create"),
        ("users.edit", "编辑用户", "user", "update"),
        ("users.delete", "删除用户", "user", "delete"),
        ("todos.view_all", "查看所有待办", "todo", "read"),
        ("todos.manage", "管理待办", "todo", "write"),
        ("audit.view", "查看审计日志", "audit", "read"),
        ("settings.manage", "管理系统设置", "setting", "write"),
        ("settings.edit", "编辑个人设置", "setting", "write"),
        ("emails.send", "发送邮件", "email", "send"),
    ]

    for perm_name, desc, resource, action in permissions_to_insert:
        conn.execute(
            "INSERT OR IGNORE INTO permissions (name, description, resource, action) VALUES (?, ?, ?, ?)",
            (perm_name, desc, resource, action),
        )

    # 插入预定义角色
    roles_config = [
        ("admin", "系统管理员，拥有全部权限"),
        ("manager", "主管，可查看和管理所有数据"),
        ("user", "普通用户，仅管理自己的数据"),
    ]

    for role_name, description in roles_config:
        conn.execute(
            "INSERT OR IGNORE INTO roles (name, description) VALUES (?, ?)",
            (role_name, description),
        )
        role = conn.execute(
            "SELECT id FROM roles WHERE name = ?", (role_name,)
        ).fetchone()
        if role:
            role_id = role["id"]
            if role_name == "admin":
                perm_names = [p[0] for p in permissions_to_insert]
            elif role_name == "manager":
                perm_names = ["users.view", "todos.view_all", "todos.manage", "emails.send"]
            else:
                perm_names = ["todos.manage", "settings.edit"]

            for perm_name in perm_names:
                perm = conn.execute(
                    "SELECT id FROM permissions WHERE name = ?", (perm_name,)
                ).fetchone()
                if perm:
                    conn.execute(
                        "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                        (role_id, perm["id"]),
                    )

    logger.info("权限表初始化完成")


def get_user_permissions(conn, user_id):
    """获取用户的完整权限列表"""
    user = conn.execute(
        "SELECT role_id, custom_permissions FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    if not user:
        return []

    # 获取角色权限
    role_perms = conn.execute(
        """
        SELECT p.name
        FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        JOIN roles r ON rp.role_id = r.id
        WHERE r.id = ?
        """,
        (user["role_id"],),
    ).fetchall()

    permissions = [p["name"] for p in role_perms]

    # 合并自定义权限
    if user["custom_permissions"]:
        try:
            custom = json.loads(user["custom_permissions"])
            if isinstance(custom, list):
                permissions.extend([p for p in custom if isinstance(p, str)])
        except (json.JSONDecodeError, TypeError):
            pass

    return list(set(permissions))


def check_permission_required(permission):
    """
    检查指定权限的装饰器
    用法: @check_permission_required('users.view')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                return jsonify({"error": "请先登录"}), 401

            conn = get_db_connection()
            user = conn.execute(
                "SELECT session_version, is_active, is_admin FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            conn.close()

            if (
                not user
                or user["is_active"] == 0
                or user["session_version"] != session.get("session_version", 0)
            ):
                session.clear()
                return jsonify({"error": "登录状态已失效，请重新登录"}), 401

            if user["is_admin"] == 1:
                return f(*args, **kwargs)

            permissions = get_user_permissions(conn, user_id)
            if permission not in permissions:
                log_permission_check(user_id, permission, False)
                return jsonify({"error": "权限不足"}), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def check_permissions_required(*permissions):
    """
    检查任意一个权限即可通过的装饰器
    用法: @check_permissions_required('users.view', 'users.edit')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                return jsonify({"error": "请先登录"}), 401

            conn = get_db_connection()
            user = conn.execute(
                "SELECT session_version, is_active, is_admin FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            conn.close()

            if (
                not user
                or user["is_active"] == 0
                or user["session_version"] != session.get("session_version", 0)
            ):
                session.clear()
                return jsonify({"error": "登录状态已失效，请重新登录"}), 401

            if user["is_admin"] == 1:
                return f(*args, **kwargs)

            perms = get_user_permissions(conn, user_id)
            if not any(p in perms for p in permissions):
                log_permission_check(user_id, list(permissions), False)
                return jsonify({"error": "权限不足"}), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def log_permission_check(user_id, permission, success, action=None, resource=None):
    """记录权限检查结果到日志"""
    from todo_app.db import get_db_connection

    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO permission_logs
            (user_id, permission, action, resource, success, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                permission if isinstance(permission, str) else ",".join(permission),
                action or (request.endpoint if hasattr(request, 'endpoint') else None),
                resource,
                1 if success else 0,
                request.remote_addr if hasattr(request, 'remote_addr') else None,
                request.headers.get('User-Agent', '')[:200] if hasattr(request, 'headers') else '',
            ),
        )
        conn.commit()
    except Exception as e:
        logger.warning(f"记录权限日志失败: {e}")
    finally:
        conn.close()


def get_all_roles():
    """获取所有角色定义"""
    return ROLES


def get_role_permissions(role_name):
    """获取角色的权限列表"""
    role = ROLES.get(role_name)
    return role["permissions"] if role else []
