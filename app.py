"""
待办事项管理系统 - 主应用文件
功能：用户注册登录、待办事项管理、邮件提醒、管理后台
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
import sqlite3
from datetime import datetime
from functools import wraps
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
import threading
import time
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
from config import Config

# 初始化 Flask 应用
app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

# 配置 Flask-Session（服务器端会话存储）
app.config["SESSION_TYPE"] = "filesystem"  # 使用文件系统存储会话
app.config["SESSION_PERMANENT"] = False  # 会话在浏览器关闭后过期
app.config["SESSION_USE_SIGNER"] = True  # 对会话cookie进行签名
app.config["SESSION_KEY_PREFIX"] = "todo_session_"  # 会话文件前缀
Session(app)

# 数据库文件名
DB_NAME = "todos.db"

# 邮件提醒定时任务状态
REMINDER_SCHEDULER_STARTED = False  # 定时任务是否已启动
REMINDER_SENT_TODAY = {}  # 记录今日已发送的邮件（避免重复发送）


def cors_response(response):
    """
    添加跨域响应头和内容安全策略
    用于处理 CORS 跨域请求和安全响应头
    """
    if hasattr(Config, "CORS_ENABLED") and Config.CORS_ENABLED:
        origin = request.headers.get("Origin", "")
        allowed_origins = getattr(Config, "ALLOWED_ORIGINS", [])

        if origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
        elif "*" in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = "*"

        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, DELETE, OPTIONS"
        )
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, Authorization, X-Requested-With"
        )
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Max-Age"] = "3600"

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
    )

    return response


@app.after_request
def after_request(response):
    return cors_response(response)


@app.route("/api/options", methods=["OPTIONS"])
def handle_options():
    response = jsonify({"status": "ok"})
    return cors_response(response)


def get_db_connection():
    """
    获取数据库连接
    返回一个支持字典式访问的 SQLite 连接对象
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    初始化数据库
    创建用户表和待办事项表（如果不存在）
    """
    conn = get_db_connection()
    conn.execute(
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed INTEGER DEFAULT 0,
            created_date DATE DEFAULT (DATE('now', 'localtime')),
            created_at TIMESTAMP DEFAULT (DATETIME('now', 'localtime')),
            user_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """
    )
    conn.commit()
    conn.close()


def hash_password(password):
    """
    密码加密函数
    使用 SHA-256 算法对密码进行哈希处理
    """
    return hashlib.sha256(password.encode()).hexdigest()


def login_required(f):
    """
    登录装饰器
    用于保护需要登录才能访问的路由
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "请先登录"}), 401
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    """
    管理员装饰器
    用于保护需要管理员权限才能访问的路由
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "请先登录"}), 401

        conn = get_db_connection()
        user = conn.execute(
            "SELECT is_admin FROM users WHERE id = ?", (session["user_id"],)
        ).fetchone()
        conn.close()

        if not user or user["is_admin"] != 1:
            return jsonify({"error": "需要管理员权限"}), 403

        return f(*args, **kwargs)

    return decorated_function


def send_email(to_email, subject, html_content):
    """
    发送邮件函数
    :param to_email: 收件人邮箱
    :param subject: 邮件主题
    :param html_content: 邮件HTML内容
    :return: 发送成功返回 True，失败返回 False
    """
    if not Config.MAIL_ENABLED or not Config.MAIL_USERNAME or not Config.MAIL_PASSWORD:
        print("邮件服务未配置或未启用")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = formataddr(("待办事项提醒", Config.MAIL_DEFAULT_SENDER))
        msg["To"] = to_email
        msg["Subject"] = subject

        html_part = MIMEText(html_content, "html", "utf-8")
        msg.attach(html_part)

        with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT) as server:
            server.starttls()
            server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
            server.send_message(msg)

        print(f"邮件已发送至: {to_email}")
        return True
    except Exception as e:
        print(f"邮件发送失败: {e}")
        return False


def generate_reset_token(user_id):
    """
    生成密码重置令牌
    :param user_id: 用户ID
    :return: 重置令牌
    """
    import secrets

    token = secrets.token_urlsafe(32)
    RESET_TOKENS[token] = {
        "user_id": user_id,
        "expires": datetime.now().timestamp() + 3600,
    }
    return token


RESET_TOKENS = {}


@app.route("/forgot-password", methods=["GET"])
def forgot_password_page():
    """
    找回密码页面
    """
    if "user_id" in session:
        if session.get("is_admin"):
            return redirect("/admin")
        return redirect("/")
    return render_template("forgot_password.html")


@app.route("/reset-password/<token>", methods=["GET"])
def reset_password_page(token):
    """
    重置密码页面
    :param token: 重置令牌
    """
    token_data = RESET_TOKENS.get(token)
    if not token_data:
        return render_template("reset_password.html", error="链接无效或已过期")

    if datetime.now().timestamp() > token_data["expires"]:
        del RESET_TOKENS[token]
        return render_template("reset_password.html", error="链接已过期")

    return render_template("reset_password.html", token=token)


@app.route("/api/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json()
    email = data.get("email", "").strip()

    if not email or "@" not in email:
        return jsonify({"error": "请提供有效的邮箱地址"}), 400

    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()

    if not user:
        return jsonify({"message": "如果邮箱存在，已发送重置链接"}), 200

    token = generate_reset_token(user["id"])
    reset_link = f"http://localhost:5145/reset-password/{token}"

    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .btn {{ display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 8px; margin: 20px 0; }}
            .footer {{ text-align: center; color: #999; margin-top: 20px; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 密码重置</h1>
            </div>
            <div class="content">
                <p>您好，{user['username']}！</p>
                <p>我们收到了您的密码重置请求。请点击下方按钮重置密码：</p>
                <p style="text-align: center;">
                    <a href="{reset_link}" class="btn">重置密码</a>
                </p>
                <p>或者复制以下链接到浏览器：</p>
                <p style="word-break: break-all; color: #667eea;">{reset_link}</p>
                <p style="color: #999;">此链接有效期为1小时，请尽快完成密码重置。</p>
            </div>
            <div class="footer">
                <p>此邮件由系统自动发送，请勿回复。</p>
            </div>
        </div>
    </body>
    </html>
    """

    success = send_email(email, "待办事项系统 - 密码重置", html_content)

    if success:
        return jsonify({"message": "如果邮箱存在，已发送重置链接"})
    else:
        return jsonify({"error": "邮件发送失败，请稍后重试"}), 500


@app.route("/api/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json()
    token = data.get("token", "").strip()
    new_password = data.get("new_password", "")

    if not token or not new_password:
        return jsonify({"error": "请提供完整的重置信息"}), 400

    if len(new_password) < 6:
        return jsonify({"error": "密码长度至少6个字符"}), 400

    token_data = RESET_TOKENS.get(token)
    if not token_data:
        return jsonify({"error": "链接无效或已过期"}), 400

    if datetime.now().timestamp() > token_data["expires"]:
        del RESET_TOKENS[token]
        return jsonify({"error": "链接已过期"}), 400

    user_id = token_data["user_id"]
    hashed_password = hash_password(new_password)

    conn = get_db_connection()
    conn.execute(
        "UPDATE users SET password = ? WHERE id = ?", (hashed_password, user_id)
    )
    conn.commit()
    conn.close()

    del RESET_TOKENS[token]

    return jsonify({"message": "密码重置成功"})


def send_reminder_emails():
    global REMINDER_SENT_TODAY

    if not Config.MAIL_ENABLED:
        return

    print("开始发送提醒邮件...")

    conn = get_db_connection()
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")

    last_reset = REMINDER_SENT_TODAY.get("date", "")
    if last_reset != current_date:
        REMINDER_SENT_TODAY = {"date": current_date}
        print("新的一天，重置发送记录")

    current_hour = now.hour

    if current_hour < 7 or current_hour > 23:
        print(f"当前时间 {current_hour}:00 不在通知时间范围内 (7:00-23:00)")
        conn.close()
        return

    users = conn.execute(
        "SELECT * FROM users WHERE email IS NOT NULL AND email != ''"
    ).fetchall()

    sent_count = 0

    for user in users:
        user_id = user["id"]
        sent_key = f"{current_date}_{user_id}_{current_hour}"
        if REMINDER_SENT_TODAY.get(sent_key):
            continue

        todos = conn.execute(
            "SELECT * FROM todos WHERE user_id = ? AND completed = 0 ORDER BY created_date DESC",
            (user["id"],),
        ).fetchall()

        if todos:
            todo_list = "\n".join([f"• {todo['title']}" for todo in todos])

            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: linear-gradient(135deg, #4A90D9 0%, #67B8DE 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                    .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                    .greeting {{ font-size: 24px; margin-bottom: 20px; }}
                    .todo-list {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                    .todo-item {{ padding: 10px 0; border-bottom: 1px solid #eee; }}
                    .todo-item:last-child {{ border-bottom: none; }}
                    .footer {{ text-align: center; color: #999; margin-top: 30px; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>📋 待办事项提醒</h1>
                    </div>
                    <div class="content">
                        <p class="greeting">你好，{user['username']}！</p>
                        <p>你共有 <strong>{len(todos)}</strong> 个待办事项未完成：</p>
                        <div class="todo-list">
                            {"".join([f'<div class="todo-item">{todo["title"]}</div>' for todo in todos])}
                        </div>
                        <p style="margin-top: 20px;">点击 <a href="http://localhost:5145">这里</a> 查看和管理你的待办事项。</p>
                    </div>
                    <div class="footer">
                        <p>此邮件由系统自动发送，请勿回复。</p>
                    </div>
                </div>
            </body>
            </html>
            """

            send_email(user["email"], f"待办事项提醒 - {current_date}", html_content)
            sent_count += 1
            REMINDER_SENT_TODAY[sent_key] = True
            print(
                f"✓ 已发送邮件给用户 {user['username']} (提醒时间: {current_hour}:00)"
            )

    conn.close()

    if sent_count > 0:
        print(f"共发送 {sent_count} 封提醒邮件")
    else:
        print("没有需要发送的提醒邮件")


def start_reminder_scheduler():
    """
    启动邮件提醒定时任务
    每隔1小时检查并发送邮件提醒
    """
    global REMINDER_SCHEDULER_STARTED
    if REMINDER_SCHEDULER_STARTED:
        return

    REMINDER_SCHEDULER_STARTED = True

    def scheduler():
        while True:
            try:
                send_reminder_emails()
            except Exception as e:
                print(f"定时任务执行失败: {e}")

            time.sleep(60)

    thread = threading.Thread(target=scheduler, daemon=True)
    thread.start()
    print("邮件提醒定时任务已启动")


@app.route("/login")
def login_page():
    if "user_id" in session:
        if session.get("is_admin"):
            return redirect("/admin")
        return redirect("/")
    return render_template("login.html")


@app.route("/register")
def register_page():
    if "user_id" in session:
        if session.get("is_admin"):
            return redirect("/admin")
        return redirect("/")
    return render_template("register.html")


@app.route("/api/check-username", methods=["GET"])
def check_username():
    username = request.args.get("username", "").strip()

    if not username:
        return jsonify({"available": False, "message": "用户名不能为空"}), 400

    if len(username) < 3:
        return jsonify({"available": False, "message": "用户名至少需要3个字符"}), 400

    conn = get_db_connection()
    existing_user = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()

    if existing_user:
        return jsonify({"available": False, "message": "用户名已被占用"})

    return jsonify({"available": True, "message": "用户名可用"})


@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()

    if (
        not data
        or not data.get("username")
        or not data.get("password")
        or not data.get("email")
    ):
        return jsonify({"error": "用户名、密码和邮箱不能为空"}), 400

    username = data["username"].strip()
    password = data["password"]
    email = data["email"].strip()

    if len(username) < 3:
        return jsonify({"error": "用户名至少需要3个字符"}), 400

    if len(password) < 6:
        return jsonify({"error": "密码至少需要6个字符"}), 400

    if not email or "@" not in email:
        return jsonify({"error": "请输入有效的邮箱地址"}), 400

    conn = get_db_connection()
    try:
        existing_user = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing_user:
            conn.close()
            return jsonify({"error": "用户名已存在"}), 400

        existing_email = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if existing_email:
            conn.close()
            return jsonify({"error": "邮箱已被注册"}), 400

        hashed_password = hash_password(password)
        cursor = conn.execute(
            "INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
            (username, hashed_password, email),
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()

        return jsonify({"id": user_id, "username": username, "email": email}), 201
    except Exception as e:
        conn.close()
        return jsonify({"error": "注册失败"}), 500


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()

    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "用户名和密码不能为空"}), 400

    username = data["username"].strip()
    password = data["password"]

    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()

    if not user:
        conn.close()
        return jsonify({"error": "用户名或密码错误"}), 401

    if user["password"] != hash_password(password):
        conn.close()
        return jsonify({"error": "用户名或密码错误"}), 401

    conn.execute(
        "UPDATE users SET last_login_at = DATETIME('now', 'localtime') WHERE id = ?",
        (user["id"],),
    )
    conn.commit()
    conn.close()

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["is_admin"] = user["is_admin"]

    return jsonify(
        {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "is_admin": bool(user["is_admin"]),
        }
    )


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "登出成功"})


@app.route("/api/me", methods=["GET"])
def get_current_user():
    if "user_id" not in session:
        return jsonify({"error": "未登录"}), 401

    conn = get_db_connection()
    user = conn.execute(
        "SELECT reminder_time FROM users WHERE id = ?", (session["user_id"],)
    ).fetchone()
    conn.close()

    reminder_time = (
        user["reminder_time"] if user and user["reminder_time"] is not None else 540
    )
    reminder_hour = reminder_time // 60
    reminder_minute = reminder_time % 60

    return jsonify(
        {
            "id": session["user_id"],
            "username": session["username"],
            "is_admin": session.get("is_admin", False),
            "reminder_time": reminder_time,
            "reminder_hour": reminder_hour,
            "reminder_minute": reminder_minute,
        }
    )


@app.route("/api/me/reminder", methods=["PUT"])
@login_required
def update_reminder_time():
    data = request.get_json()
    reminder_hour = data.get("reminder_hour")
    reminder_minute = data.get("reminder_minute", 0)

    if reminder_hour is None:
        return jsonify({"error": "请提供提醒时间"}), 400

    try:
        reminder_hour = int(reminder_hour)
        reminder_minute = int(reminder_minute) if reminder_minute is not None else 0

        if reminder_hour < 0 or reminder_hour > 23:
            return jsonify({"error": "小时必须是0-23之间的整数"}), 400
        if reminder_minute < 0 or reminder_minute > 59:
            return jsonify({"error": "分钟必须是0-59之间的整数"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "请提供有效的提醒时间"}), 400

    reminder_time = reminder_hour * 60 + reminder_minute

    conn = get_db_connection()
    conn.execute(
        "UPDATE users SET reminder_time = ? WHERE id = ?",
        (reminder_time, session["user_id"]),
    )
    conn.commit()
    conn.close()

    return jsonify(
        {
            "message": "提醒时间已更新",
            "reminder_time": reminder_time,
            "reminder_hour": reminder_hour,
            "reminder_minute": reminder_minute,
        }
    )


@app.route("/")
def index():
    """
    首页路由
    显示待办事项管理页面
    """
    if "user_id" not in session:
        return redirect("/login")

    if session.get("is_admin"):
        return redirect("/admin")

    return render_template("index.html")


@app.route("/api/todos", methods=["GET"])
@login_required
def get_todos():
    """
    获取待办事项列表API
    根据日期筛选返回用户的待办事项
    """
    try:
        date = request.args.get("date")
        user_id = session["user_id"]
        conn = get_db_connection()

        if date:
            todos = conn.execute(
                "SELECT * FROM todos WHERE created_date = ? AND user_id = ? ORDER BY created_at DESC",
                (date, user_id),
            ).fetchall()
        else:
            todos = conn.execute(
                "SELECT * FROM todos WHERE user_id = ? AND completed = 0 ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()

        conn.close()

        result = []
        for todo in todos:
            result.append(
                {
                    "id": todo["id"],
                    "title": todo["title"],
                    "description": todo["description"],
                    "completed": bool(todo["completed"]),
                    "created_date": todo["created_date"],
                    "created_at": todo["created_at"],
                }
            )

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/todos", methods=["POST"])
@login_required
def add_todo():
    """
    添加待办事项API
    创建新的待办事项
    """
    data = request.get_json()

    if not data or not data.get("title"):
        return jsonify({"error": "标题不能为空"}), 400

    title = data["title"].strip()
    description = data.get("description", "").strip()
    user_id = session["user_id"]

    conn = get_db_connection()
    cursor = conn.execute(
        "INSERT INTO todos (title, description, user_id, created_date) VALUES (?, ?, ?, ?)",
        (title, description, user_id, datetime.now().strftime("%Y-%m-%d")),
    )
    conn.commit()
    todo_id = cursor.lastrowid
    conn.close()

    return (
        jsonify(
            {
                "id": todo_id,
                "title": title,
                "description": description,
                "completed": False,
                "created_date": datetime.now().strftime("%Y-%m-%d"),
            }
        ),
        201,
    )


@app.route("/api/todos/<int:todo_id>", methods=["PUT"])
@login_required
def update_todo(todo_id):
    """
    更新待办事项API
    修改待办事项的完成状态
    """
    data = request.get_json()
    user_id = session["user_id"]

    conn = get_db_connection()
    todo = conn.execute(
        "SELECT * FROM todos WHERE id = ? AND user_id = ?", (todo_id, user_id)
    ).fetchone()

    if not todo:
        conn.close()
        return jsonify({"error": "待办事项不存在"}), 404

    if "completed" in data:
        conn.execute(
            "UPDATE todos SET completed = ? WHERE id = ?",
            (1 if data["completed"] else 0, todo_id),
        )

    if "title" in data:
        conn.execute(
            "UPDATE todos SET title = ? WHERE id = ?", (data["title"].strip(), todo_id)
        )

    if "description" in data:
        conn.execute(
            "UPDATE todos SET description = ? WHERE id = ?",
            (data["description"].strip(), todo_id),
        )

    conn.commit()
    updated_todo = conn.execute(
        "SELECT * FROM todos WHERE id = ?", (todo_id,)
    ).fetchone()
    conn.close()

    return jsonify(
        {
            "id": updated_todo["id"],
            "title": updated_todo["title"],
            "description": updated_todo["description"],
            "completed": bool(updated_todo["completed"]),
            "created_date": updated_todo["created_date"],
            "created_at": updated_todo["created_at"],
        }
    )


@app.route("/api/todos/<int:todo_id>", methods=["DELETE"])
@login_required
def delete_todo(todo_id):
    """
    删除待办事项API
    删除指定的待办事项
    """
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.execute(
        "DELETE FROM todos WHERE id = ? AND user_id = ?", (todo_id, user_id)
    )
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        return jsonify({"error": "待办事项不存在"}), 404

    return jsonify({"message": "删除成功"})


@app.route("/admin")
def admin_page():
    """
    管理后台页面
    显示用户管理和系统设置
    """
    if "user_id" not in session:
        return redirect("/login")

    if not session.get("is_admin"):
        return redirect("/")

    return render_template("admin.html")


@app.route("/api/admin/users", methods=["GET"])
@admin_required
def get_users():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    search = request.args.get("search", "").strip()

    conn = get_db_connection()

    query = "SELECT * FROM users WHERE 1=1"
    params = []

    if search:
        query += " AND (username LIKE ? OR email LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])

    users = conn.execute(query, params).fetchall()

    count_query = "SELECT COUNT(*) FROM users WHERE 1=1"
    count_params = []
    if search:
        count_query += " AND (username LIKE ? OR email LIKE ?)"
        count_params.extend([f"%{search}%", f"%{search}%"])

    total = conn.execute(count_query, count_params).fetchone()[0]
    conn.close()

    result = []
    for user in users:
        temp_conn = get_db_connection()
        todo_count = temp_conn.execute(
            "SELECT COUNT(*) FROM todos WHERE user_id = ?", (user["id"],)
        ).fetchone()[0]
        temp_conn.close()

        result.append(
            {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "is_admin": bool(user["is_admin"]),
                "created_at": user["created_at"],
                "last_login_at": user["last_login_at"],
                "todo_count": todo_count,
            }
        )

    return jsonify(
        {
            "users": result,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
        }
    )


@app.route("/api/admin/users/<int:user_id>", methods=["GET"])
@admin_required
def get_user_detail(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    if not user:
        conn.close()
        return jsonify({"error": "用户不存在"}), 404

    todos = conn.execute(
        "SELECT * FROM todos WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()

    todo_list = []
    for todo in todos:
        todo_list.append(
            {
                "id": todo["id"],
                "title": todo["title"],
                "description": todo["description"],
                "completed": bool(todo["completed"]),
                "created_date": todo["created_date"],
                "created_at": todo["created_at"],
            }
        )

    return jsonify(
        {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "is_admin": bool(user["is_admin"]),
            "created_at": user["created_at"],
            "last_login_at": user["last_login_at"],
            "todos": todo_list,
        }
    )


@app.route("/api/admin/users", methods=["POST"])
@admin_required
def create_user():
    data = request.get_json()

    if (
        not data
        or not data.get("username")
        or not data.get("password")
        or not data.get("email")
    ):
        return jsonify({"error": "用户名、密码和邮箱不能为空"}), 400

    username = data["username"].strip()
    password = data["password"]
    email = data["email"].strip()
    is_admin = data.get("is_admin", False)

    if len(username) < 3:
        return jsonify({"error": "用户名至少需要3个字符"}), 400

    if len(password) < 6:
        return jsonify({"error": "密码至少需要6个字符"}), 400

    if not email or "@" not in email:
        return jsonify({"error": "请输入有效的邮箱地址"}), 400

    conn = get_db_connection()
    try:
        existing_user = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing_user:
            conn.close()
            return jsonify({"error": "用户名已存在"}), 400

        existing_email = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if existing_email:
            conn.close()
            return jsonify({"error": "邮箱已被注册"}), 400

        hashed_password = hash_password(password)
        cursor = conn.execute(
            "INSERT INTO users (username, password, email, is_admin) VALUES (?, ?, ?, ?)",
            (username, hashed_password, email, 1 if is_admin else 0),
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()

        return (
            jsonify(
                {
                    "id": user_id,
                    "username": username,
                    "email": email,
                    "is_admin": is_admin,
                }
            ),
            201,
        )
    except Exception as e:
        conn.close()
        return jsonify({"error": "创建用户失败"}), 500


@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    if user_id == session["user_id"]:
        return jsonify({"error": "不能删除自己的账户"}), 400

    conn = get_db_connection()
    cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        return jsonify({"error": "用户不存在"}), 404

    return jsonify({"message": "删除成功"})


@app.route("/api/admin/users/<int:user_id>/todos", methods=["GET"])
@admin_required
def get_user_todos(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    if not user:
        conn.close()
        return jsonify({"error": "用户不存在"}), 404

    todos = conn.execute(
        "SELECT * FROM todos WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()

    result = []
    for todo in todos:
        result.append(
            {
                "id": todo["id"],
                "title": todo["title"],
                "description": todo["description"],
                "completed": bool(todo["completed"]),
                "created_date": todo["created_date"],
                "created_at": todo["created_at"],
            }
        )

    return jsonify(result)


@app.route("/api/admin/test-email", methods=["POST"])
@admin_required
def test_email():
    data = request.get_json()
    email = data.get("email", "").strip()

    if not email or "@" not in email:
        return jsonify({"error": "请提供有效的邮箱地址"}), 400

    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #667eea;">✅ 邮件测试成功！</h2>
            <p>这是一封测试邮件，用于验证邮件服务配置是否正确。</p>
            <p>发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <hr>
            <p style="color: #666; font-size: 12px;">
                此邮件由待办事项系统自动发送，请勿回复。
            </p>
        </body>
    </html>
    """

    success = send_email(email, "待办事项系统 - 邮件测试", html_content)

    if success:
        return jsonify({"message": f"测试邮件已发送到 {email}"})
    else:
        return jsonify({"error": "邮件发送失败，请检查配置"}), 500


@app.route("/api/send-reminder-now", methods=["POST"])
@login_required
def send_reminder_now():
    if not Config.MAIL_ENABLED:
        return jsonify({"error": "邮件服务未启用"}), 400

    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?", (session["user_id"],)
    ).fetchone()

    if not user or not user["email"]:
        conn.close()
        return jsonify({"error": "用户未设置邮箱"}), 400

    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")

    todos = conn.execute(
        "SELECT * FROM todos WHERE user_id = ? AND completed = 0 ORDER BY created_date DESC",
        (user["id"],),
    ).fetchall()

    conn.close()

    if not todos:
        return jsonify({"message": "没有未完成的待办事项"})

    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #4A90D9 0%, #67B8DE 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .greeting {{ font-size: 24px; margin-bottom: 20px; }}
            .todo-list {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .todo-item {{ padding: 10px 0; border-bottom: 1px solid #eee; }}
            .todo-item:last-child {{ border-bottom: none; }}
            .footer {{ text-align: center; color: #999; margin-top: 30px; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📋 待办事项提醒</h1>
            </div>
            <div class="content">
                <p class="greeting">你好，{user['username']}！</p>
                <p>今天是 {current_date}，你还有 <strong>{len(todos)}</strong> 个待办事项未完成：</p>
                <div class="todo-list">
                    {"".join([f'<div class="todo-item">{todo["title"]}</div>' for todo in todos])}
                </div>
                <p style="margin-top: 20px;">点击 <a href="http://localhost:5145">这里</a> 查看和管理你的待办事项。</p>
            </div>
            <div class="footer">
                <p>此邮件由系统自动发送，请勿回复。</p>
            </div>
        </div>
    </body>
    </html>
    """

    send_email(user["email"], f"待办事项提醒 - {current_date}", html_content)

    return jsonify({"message": f"提醒邮件已发送到 {user['email']}"})


if __name__ == "__main__":
    init_db()
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        start_reminder_scheduler()
    app.run(debug=True, host="0.0.0.0", port=5145)
