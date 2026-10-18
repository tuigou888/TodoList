"""
待办事项管理系统 - 主应用文件
功能：用户注册登录、待办事项管理、邮件提醒、管理后台
"""

import os
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# 设置时区为中国标准时间
os.environ["TZ"] = "Asia/Shanghai"

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
import hashlib
import hmac
import re
import smtplib
from html import escape as html_escape
from werkzeug.security import check_password_hash, generate_password_hash
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
import threading
import time
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

# 会话 Cookie 与请求体安全配置
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "False").lower() in [
    "true",
    "1",
    "t",
]
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = os.environ.get(
    "SESSION_COOKIE_SAMESITE", "Lax"
)
app.config["SESSION_COOKIE_SECURE"] = SESSION_COOKIE_SECURE
app.config["MAX_CONTENT_LENGTH"] = int(
    os.environ.get("MAX_CONTENT_LENGTH", 2 * 1024 * 1024)
)
Session(app)

# 数据库文件名
DB_NAME = "todos.db"

# 站点的对外访问地址（用于邮件里的链接），生产环境必须配置
BASE_URL = os.environ.get("BASE_URL", "http://localhost:5145").rstrip("/")

# 已知的不安全默认密钥，启动时拒绝使用
INSECURE_SECRET_KEYS = {
    "your-secret-key-change-this-in-production",
    "your-very-long-and-random-secret-key-change-this-in-production",
    "your-secret-key-here",
    "secret",
    "dev",
    "test",
}

# 请求体大小上限的友好提示
MAX_CONTENT_LENGTH = app.config["MAX_CONTENT_LENGTH"]

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
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    # 每个连接都必须开启外键约束（SQLite 默认关闭）
    conn.execute("PRAGMA foreign_keys = ON")
    # 并发写入时等待锁释放，而不是立刻抛 database is locked
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


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
            created_date DATE,
            created_at TIMESTAMP,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """
    )

    # 常用查询索引：按用户、完成状态、日期检索
    conn.execute("CREATE INDEX IF NOT EXISTS idx_todos_user_id ON todos(user_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_todos_user_completed ON todos(user_id, completed)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_todos_user_date ON todos(user_id, created_date)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")

    conn.commit()
    conn.close()


def hash_password(password):
    """
    密码加密函数
    使用 Werkzeug 的安全哈希（默认 scrypt，自带随机 salt）
    """
    return generate_password_hash(password)


def legacy_hash_password(password):
    """
    旧版无盐 SHA-256，仅用于校验历史密码并在登录后自动升级
    """
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(stored_hash, password):
    """
    校验密码。
    返回 (是否匹配, 是否需要升级哈希)
    """
    if not stored_hash:
        return False, False

    try:
        if check_password_hash(stored_hash, password):
            return True, False
    except (ValueError, TypeError):
        # 历史 SHA-256 哈希不是 Werkzeug 格式，会在这里失败
        pass

    if isinstance(stored_hash, str) and re.fullmatch(r"[0-9a-f]{64}", stored_hash):
        if hmac.compare_digest(stored_hash, legacy_hash_password(password)):
            return True, True

    return False, False


def validate_config(strict=None):
    """
    校验关键配置。
    strict=True 时配置错误直接抛异常（生产环境），False 时仅告警（本地开发）。
    """
    if strict is None:
        strict = not app.debug

    secret_key = Config.SECRET_KEY or ""
    if secret_key in INSECURE_SECRET_KEYS or len(secret_key) < 16:
        message = (
            "SECRET_KEY 未配置或过于简单，请在 .env 中设置至少 16 位的随机字符串"
        )
        if strict:
            raise RuntimeError(message)
        logger.warning(message)


def login_required(f):
    """
    登录装饰器
    用于保护需要登录才能访问的路由
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "请先登录"}), 401

        # 校验用户仍然存在：被删除用户的旧会话必须立即失效
        conn = get_db_connection()
        user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()

        if not user:
            session.clear()
            return jsonify({"error": "登录状态已失效，请重新登录"}), 401

        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    """
    管理员装饰器
    用于保护需要管理员权限才能访问的路由
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "请先登录"}), 401

        conn = get_db_connection()
        user = conn.execute(
            "SELECT is_admin FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        conn.close()

        if not user:
            session.clear()
            return jsonify({"error": "登录状态已失效，请重新登录"}), 401

        if user["is_admin"] != 1:
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
        logger.warning("邮件服务未配置或未启用")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = formataddr(("待办事项提醒", Config.MAIL_DEFAULT_SENDER))
        msg["To"] = to_email
        msg["Subject"] = subject

        html_part = MIMEText(html_content, "html", "utf-8")
        msg.attach(html_part)

        # 465 端口通常是 SSL 直连，587 端口才使用 STARTTLS
        use_ssl = bool(getattr(Config, "MAIL_USE_SSL", False)) or (
            Config.MAIL_PORT == 465 and not Config.MAIL_USE_TLS
        )
        timeout = getattr(Config, "MAIL_TIMEOUT", 15)
        if use_ssl:
            server = smtplib.SMTP_SSL(
                Config.MAIL_SERVER, Config.MAIL_PORT, timeout=timeout
            )
        else:
            server = smtplib.SMTP(
                Config.MAIL_SERVER, Config.MAIL_PORT, timeout=timeout
            )

        with server:
            if Config.MAIL_USE_TLS and not use_ssl:
                server.starttls()
            server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
            server.send_message(msg)

        # 收件人邮箱属于个人信息，只在 DEBUG 级别记录
        logger.debug("邮件已发送至: %s", to_email)
        logger.info("提醒邮件发送成功")
        return True
    except Exception as e:
        logger.error("邮件发送失败: %s", e)
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
    data = read_json_object()
    if data is None:
        return jsonify({"error": "请求必须是 JSON 对象"}), 400

    email, error = validate_email(data.get("email"))
    if error:
        return jsonify({"error": error}), 400

    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE LOWER(email) = ?", (email,)
    ).fetchone()
    conn.close()

    if not user:
        return jsonify({"message": "如果邮箱存在，已发送重置链接"}), 200

    token = generate_reset_token(user["id"])
    reset_link = f"{BASE_URL}/reset-password/{token}"

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
                <p>您好，{html_escape(user['username'])}！</p>
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
    data = read_json_object()
    if data is None:
        return jsonify({"error": "请求必须是 JSON 对象"}), 400

    token = data.get("token", "")
    if not isinstance(token, str) or not token.strip():
        return jsonify({"error": "请提供完整的重置信息"}), 400
    token = token.strip()

    new_password, error = validate_password(data.get("new_password"))
    if error:
        return jsonify({"error": error}), 400

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


# ==================== 输入校验 ====================

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fa5-]{3,32}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_TODO_TITLE = 200
MAX_TODO_DESCRIPTION = 2000


def normalize_email(email):
    """邮箱统一小写存储与查询，避免大小写导致重复账号"""
    return (email or "").strip().lower()


def validate_username(username):
    username = (username or "").strip()
    if not USERNAME_PATTERN.fullmatch(username):
        return None, "用户名需为3-32位字母、数字、下划线、中文或连字符"
    return username, None


def validate_email(email):
    email = normalize_email(email)
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        return None, "请输入有效的邮箱地址"
    return email, None


def validate_password(password):
    if not isinstance(password, str) or len(password) < 6:
        return None, "密码至少需要6个字符"
    if len(password) > 128:
        return None, "密码不能超过128个字符"
    return password, None


def validate_text(value, field_name, max_length, required=False):
    if value is None:
        value = ""
    if not isinstance(value, str):
        return None, f"{field_name}必须是文本"
    value = value.strip()
    if required and not value:
        return None, f"{field_name}不能为空"
    if len(value) > max_length:
        return None, f"{field_name}不能超过{max_length}个字符"
    return value, None


def read_json_object():
    """读取 JSON 请求体；非对象或格式错误时返回 None，由调用方返回 400"""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


# ==================== 统一错误响应 ====================

CLIENT_ERROR_MESSAGES = {
    400: "请求格式错误",
    404: "资源不存在",
    405: "请求方法不允许",
    413: "请求体过大",
    415: "请求必须是 JSON 格式",
}


def wants_json_response():
    return request.path.startswith("/api/")


@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(405)
@app.errorhandler(413)
@app.errorhandler(415)
def handle_client_error(error):
    if wants_json_response():
        message = CLIENT_ERROR_MESSAGES.get(error.code, "请求无效")
        return jsonify({"error": message}), error.code
    return error


@app.errorhandler(500)
def handle_server_error(error):
    logger.error("未处理异常: %s", error, exc_info=True)
    if wants_json_response():
        return jsonify({"error": "服务器内部错误"}), 500
    return "服务器内部错误", 500


def format_time_ago(created_at_str):
    """
    格式化时间差，显示已过去多久
    """
    try:
        created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        diff = now - created_at

        days = diff.days
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60

        if days > 0:
            return f"{days}天前"
        elif hours > 0:
            return f"{hours}小时前"
        elif minutes > 0:
            return f"{minutes}分钟前"
        else:
            return "刚刚"
    except:
        return "未知"


def send_reminder_emails():
    """
    发送邮件提醒
    每天7:30-21:30每小时检查一次，通知用户未完成的待办事项
    """
    global REMINDER_SENT_TODAY

    if not Config.MAIL_ENABLED:
        return

    logger.info("开始发送提醒邮件...")

    conn = get_db_connection()
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_hour = now.hour
    current_minute = now.minute

    # 检查是否在通知时间范围内 (7:30-21:30)
    # 7:30 开始，21:30 结束
    is_before_start = current_hour < 7 or (current_hour == 7 and current_minute < 30)
    is_after_end = current_hour > 21 or (current_hour == 21 and current_minute > 30)

    if is_before_start or is_after_end:
        logger.info(
            f"当前时间 {current_hour}:{current_minute:02d} 不在通知时间范围内 (7:30-21:30)"
        )
        conn.close()
        return

    # 新的一天，重置发送记录
    last_reset = REMINDER_SENT_TODAY.get("date", "")
    if last_reset != current_date:
        REMINDER_SENT_TODAY = {"date": current_date}
        logger.info("新的一天，重置发送记录")

    users = conn.execute(
        "SELECT * FROM users WHERE email IS NOT NULL AND email != ''"
    ).fetchall()

    sent_count = 0

    for user in users:
        user_id = user["id"]
        sent_key = f"{current_date}_{user_id}_{current_hour}"
        if REMINDER_SENT_TODAY.get(sent_key):
            continue

        # 获取未完成的待办事项
        todos = conn.execute(
            "SELECT * FROM todos WHERE user_id = ? AND completed = 0 ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()

        if todos:
            # 构建待办事项列表，包含创建时间和已过去时间
            todo_items_html = ""
            for todo in todos:
                created_at = todo["created_at"]
                time_ago = format_time_ago(created_at)
                todo_items_html += f"""
                <div class="todo-item">
                    <div class="todo-title">{html_escape(todo["title"])}</div>
                    <div class="todo-meta">
                        <span class="todo-date">创建于: {html_escape(str(created_at or ""))}</span>
                        <span class="time-ago">已过去: {time_ago}</span>
                    </div>
                </div>
                """

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
                    .todo-item {{ padding: 15px 0; border-bottom: 1px solid #eee; }}
                    .todo-item:last-child {{ border-bottom: none; }}
                    .todo-title {{ font-weight: 600; font-size: 16px; margin-bottom: 8px; }}
                    .todo-meta {{ font-size: 13px; color: #666; }}
                    .todo-date {{ margin-right: 15px; }}
                    .time-ago {{ color: #e74c3c; font-weight: 500; }}
                    .footer {{ text-align: center; color: #999; margin-top: 30px; font-size: 12px; }}
                    .notification-time {{ background: #fff3cd; padding: 10px; border-radius: 6px; margin-bottom: 20px; font-size: 14px; color: #856404; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>📋 待办事项提醒</h1>
                    </div>
                    <div class="content">
                        <p class="greeting">你好，{html_escape(user['username'])}！</p>
                        <div class="notification-time">
                            ⏰ 当前时间: {now.strftime("%Y-%m-%d %H:%M")} | 提醒时段: 07:00-23:00
                        </div>
                        <p>您共有 <strong>{len(todos)}</strong> 个待办事项未完成：</p>
                        <div class="todo-list">
                            {todo_items_html}
                        </div>
                        <p style="margin-top: 20px;">点击 <a href="{BASE_URL}">这里</a> 查看和管理您的待办事项。</p>
                    </div>
                    <div class="footer">
                        <p>此邮件由系统自动发送，请勿回复。</p>
                        <p>每日提醒时间: 07:00 - 23:00 (每小时检查一次)</p>
                    </div>
                </div>
            </body>
            </html>
            """

            send_email(
                user["email"],
                f"待办事项提醒 - {current_date} {current_hour}:00",
                html_content,
            )
            sent_count += 1
            REMINDER_SENT_TODAY[sent_key] = True
            logger.info(
                f"✓ 已发送邮件给用户 {user['username']} (提醒时间: {current_hour}:00)"
            )

    conn.close()

    if sent_count > 0:
        logger.info(f"共发送 {sent_count} 封提醒邮件")
    else:
        logger.info("没有需要发送的提醒邮件")


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
            now = datetime.now()
            current_minute = now.minute
            current_second = now.second

            # 计算距离下一个整点（北京时间）的秒数
            # 如果现在是 10:15:30，距离 11:00:00 还有 (44 * 60 + 30) = 2670 秒
            seconds_to_next_hour = (59 - current_minute) * 60 + (60 - current_second)

            logger.info(
                f"当前时间: {now.strftime('%H:%M:%S')}，距离下一个整点还有 {seconds_to_next_hour} 秒"
            )

            # 等待到下一个整点
            time.sleep(seconds_to_next_hour)

            # 到达整点，执行邮件发送
            try:
                send_reminder_emails()
            except Exception as e:
                logger.error(f"定时任务执行失败: {e}")

            # 等待1分钟，避免在同一分钟内重复执行
            time.sleep(60)

    thread = threading.Thread(target=scheduler, daemon=True)
    thread.start()
    logger.info("邮件提醒定时任务已启动")


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

    if not USERNAME_PATTERN.fullmatch(username):
        return (
            jsonify(
                {
                    "available": False,
                    "message": "用户名需为3-32位字母、数字、下划线、中文或连字符",
                }
            ),
            400,
        )

    conn = get_db_connection()
    existing_user = conn.execute(
        "SELECT id FROM users WHERE LOWER(username) = LOWER(?)", (username,)
    ).fetchone()
    conn.close()

    if existing_user:
        return jsonify({"available": False, "message": "用户名已被占用"})

    return jsonify({"available": True, "message": "用户名可用"})


@app.route("/api/register", methods=["POST"])
def register():
    data = read_json_object()
    if data is None:
        return jsonify({"error": "请求必须是 JSON 对象"}), 400

    username, error = validate_username(data.get("username"))
    if error:
        return jsonify({"error": error}), 400

    password, error = validate_password(data.get("password"))
    if error:
        return jsonify({"error": error}), 400

    email, error = validate_email(data.get("email"))
    if error:
        return jsonify({"error": error}), 400

    conn = get_db_connection()
    try:
        existing_user = conn.execute(
            "SELECT id FROM users WHERE LOWER(username) = LOWER(?)", (username,)
        ).fetchone()
        if existing_user:
            conn.close()
            return jsonify({"error": "用户名已存在"}), 400

        existing_email = conn.execute(
            "SELECT id FROM users WHERE LOWER(email) = ?", (email,)
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
    except Exception:
        conn.close()
        logger.exception("注册失败")
        return jsonify({"error": "注册失败"}), 500


@app.route("/api/login", methods=["POST"])
def login():
    data = read_json_object()
    if data is None:
        return jsonify({"error": "请求必须是 JSON 对象"}), 400

    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "用户名和密码不能为空"}), 400

    username = username.strip()
    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400

    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()

    if not user:
        conn.close()
        return jsonify({"error": "用户名或密码错误"}), 401

    matched, needs_rehash = verify_password(user["password"], password)
    if not matched:
        conn.close()
        return jsonify({"error": "用户名或密码错误"}), 401

    # 历史 SHA-256 哈希在用户登录成功后自动升级为 Werkzeug 哈希
    if needs_rehash:
        conn.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (hash_password(password), user["id"]),
        )

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
@login_required
def get_current_user():
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
            "is_admin": bool(session.get("is_admin", False)),
            "reminder_time": reminder_time,
            "reminder_hour": reminder_hour,
            "reminder_minute": reminder_minute,
        }
    )


@app.route("/api/me/reminder", methods=["PUT"])
@login_required
def update_reminder_time():
    data = read_json_object()
    if data is None:
        return jsonify({"error": "请求必须是 JSON 对象"}), 400

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
        view = request.args.get("view", "today")  # today 或 all
        user_id = session["user_id"]
        conn = get_db_connection()

        if date:
            # 指定日期的查询
            todos = conn.execute(
                "SELECT * FROM todos WHERE created_date = ? AND user_id = ? ORDER BY created_at DESC",
                (date, user_id),
            ).fetchall()
        elif view == "all":
            # 所有待办（已完成 + 未完成）
            todos = conn.execute(
                "SELECT * FROM todos WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        else:
            # 默认只返回未完成的
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
    data = read_json_object()
    if data is None:
        return jsonify({"error": "请求必须是 JSON 对象"}), 400

    title, error = validate_text(
        data.get("title"), "标题", MAX_TODO_TITLE, required=True
    )
    if error:
        return jsonify({"error": error}), 400

    description, error = validate_text(
        data.get("description"), "描述", MAX_TODO_DESCRIPTION
    )
    if error:
        return jsonify({"error": error}), 400

    user_id = session["user_id"]

    now = datetime.now()
    created_date = now.strftime("%Y-%m-%d")
    created_at = now.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.execute(
        "INSERT INTO todos (title, description, user_id, created_date, created_at) VALUES (?, ?, ?, ?, ?)",
        (title, description, user_id, created_date, created_at),
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
                "created_date": created_date,
                "created_at": created_at,
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
    data = read_json_object()
    if data is None:
        return jsonify({"error": "请求必须是 JSON 对象"}), 400

    user_id = session["user_id"]

    conn = get_db_connection()
    todo = conn.execute(
        "SELECT * FROM todos WHERE id = ? AND user_id = ?", (todo_id, user_id)
    ).fetchone()

    if not todo:
        conn.close()
        return jsonify({"error": "待办事项不存在"}), 404

    updates = {}

    if "completed" in data:
        if not isinstance(data["completed"], bool):
            conn.close()
            return jsonify({"error": "completed 必须是布尔值"}), 400
        updates["completed"] = 1 if data["completed"] else 0

    if "title" in data:
        title, error = validate_text(
            data["title"], "标题", MAX_TODO_TITLE, required=True
        )
        if error:
            conn.close()
            return jsonify({"error": error}), 400
        updates["title"] = title

    if "description" in data:
        description, error = validate_text(
            data["description"], "描述", MAX_TODO_DESCRIPTION
        )
        if error:
            conn.close()
            return jsonify({"error": error}), 400
        updates["description"] = description

    if updates:
        assignments = ", ".join(f"{field} = ?" for field in updates)
        conn.execute(
            f"UPDATE todos SET {assignments} WHERE id = ?",
            (*updates.values(), todo_id),
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
    page = request.args.get("page", 1, type=int) or 1
    page = max(page, 1)
    per_page = request.args.get("per_page", 10, type=int) or 10
    per_page = min(max(per_page, 1), 100)
    search = (request.args.get("search", "") or "").strip()[:100]

    conn = get_db_connection()

    query = """
        SELECT u.*,
               (SELECT COUNT(*) FROM todos t WHERE t.user_id = u.id) AS todo_count
        FROM users u
        WHERE 1=1
    """
    params = []

    if search:
        query += " AND (u.username LIKE ? OR u.email LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY u.created_at DESC LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])

    users = conn.execute(query, params).fetchall()

    count_query = "SELECT COUNT(*) FROM users u WHERE 1=1"
    count_params = []
    if search:
        count_query += " AND (u.username LIKE ? OR u.email LIKE ?)"
        count_params.extend([f"%{search}%", f"%{search}%"])

    total = conn.execute(count_query, count_params).fetchone()[0]
    conn.close()

    result = []
    for user in users:
        result.append(
            {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "is_admin": bool(user["is_admin"]),
                "created_at": user["created_at"],
                "last_login_at": user["last_login_at"],
                "todo_count": user["todo_count"],
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
    data = read_json_object()
    if data is None:
        return jsonify({"error": "请求必须是 JSON 对象"}), 400

    username, error = validate_username(data.get("username"))
    if error:
        return jsonify({"error": error}), 400

    password, error = validate_password(data.get("password"))
    if error:
        return jsonify({"error": error}), 400

    email, error = validate_email(data.get("email"))
    if error:
        return jsonify({"error": error}), 400

    is_admin = data.get("is_admin", False)
    if not isinstance(is_admin, bool):
        return jsonify({"error": "is_admin 必须是布尔值"}), 400

    conn = get_db_connection()
    try:
        existing_user = conn.execute(
            "SELECT id FROM users WHERE LOWER(username) = LOWER(?)", (username,)
        ).fetchone()
        if existing_user:
            conn.close()
            return jsonify({"error": "用户名已存在"}), 400

        existing_email = conn.execute(
            "SELECT id FROM users WHERE LOWER(email) = ?", (email,)
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
    except Exception:
        conn.close()
        logger.exception("创建用户失败")
        return jsonify({"error": "创建用户失败"}), 500


@app.route("/api/admin/users/<int:user_id>/password", methods=["PUT"])
@admin_required
def reset_user_password(user_id):
    """
    管理员重置用户密码
    """
    data = read_json_object()
    if data is None:
        return jsonify({"error": "请求必须是 JSON 对象"}), 400

    new_password, error = validate_password(data.get("password"))
    if error:
        return jsonify({"error": error}), 400

    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT id, username FROM users WHERE id = ?", (user_id,)
        ).fetchone()

        if not user:
            conn.close()
            return jsonify({"error": "用户不存在"}), 404

        hashed_password = hash_password(new_password)
        conn.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (hashed_password, user_id),
        )
        conn.commit()
        conn.close()

        return jsonify({"message": f"用户 {user['username']} 的密码已重置"})
    except Exception as e:
        conn.close()
        return jsonify({"error": "重置密码失败"}), 500


@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    if user_id == session["user_id"]:
        return jsonify({"error": "不能删除自己的账户"}), 400

    conn = get_db_connection()
    try:
        user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return jsonify({"error": "用户不存在"}), 404

        # 先删待办再删用户：兼容历史数据库（外键可能未启用级联）
        conn.execute("DELETE FROM todos WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()

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
    data = read_json_object()
    if data is None:
        return jsonify({"error": "请求必须是 JSON 对象"}), 400

    email, error = validate_email(data.get("email"))
    if error:
        return jsonify({"error": error}), 400

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
                <p class="greeting">你好，{html_escape(user['username'])}！</p>
                <p>今天是 {current_date}，你还有 <strong>{len(todos)}</strong> 个待办事项未完成：</p>
                <div class="todo-list">
                    {"".join([f'<div class="todo-item">{html_escape(todo["title"])}</div>' for todo in todos])}
                </div>
                <p style="margin-top: 20px;">点击 <a href="{BASE_URL}">这里</a> 查看和管理你的待办事项。</p>
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
    validate_config(strict=False)
    app.run(debug=True, host="0.0.0.0", port=5145)


# Gunicorn 启动钩子（在 Gunicorn 环境下启动定时任务）
def on_starting(server):
    """Gunicorn 启动时调用"""
    logger.info("Gunicorn 正在启动...")
    init_db()
    start_reminder_scheduler()


def when_ready(server):
    """Gunicorn 准备好接受请求时调用"""
    logger.info("Gunicorn 已就绪")
