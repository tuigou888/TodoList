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

from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_session import Session
import csv
import io
import json
import secrets
from datetime import datetime, timedelta
from functools import wraps
from html import escape as html_escape
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
from config import Config

from todo_app.audit import log_audit
from todo_app.db import get_db_connection, init_db, now_string
from todo_app.mailer import build_daily_review_email, send_email
from todo_app.outbox import (
    EMAIL_MAX_ATTEMPTS,
    enqueue_email,
    process_email_outbox,
)
from todo_app.scheduler import (
    send_manual_reminder,
    send_scheduled_reminders,
    start_reminder_scheduler,
)
from todo_app.reviews import (
    collect_review_stats,
    send_daily_reviews,
    send_weekly_reviews,
)
from todo_app.tokens import (
    generate_reset_token,
    get_reset_token,
    reset_password_with_token,
    reset_request_allowed,
)
from todo_app.security import (
    hash_password,
    hash_reset_token,
    legacy_hash_password,
    verify_password,
)
from todo_app.nlp import parse_natural
from todo_app.validators import (
    MAX_TODO_DESCRIPTION,
    MAX_TODO_TITLE,
    USERNAME_PATTERN,
    VALID_PRIORITIES,
    read_json_object,
    serialize_todo,
    validate_context,
    validate_date,
    validate_email,
    validate_password,
    validate_priority,
    validate_tags,
    validate_text,
    validate_time,
    validate_username,
)

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

# 登录失败限流
LOGIN_MAX_FAILURES = 5  # 窗口内允许的最大失败次数
LOGIN_WINDOW_SECONDS = 900  # 统计窗口：15 分钟
LOGIN_LOCK_SECONDS = 900  # 触发后的锁定时长：15 分钟



def cors_response(response):
    """
    添加跨域响应头和内容安全策略
    用于处理 CORS 跨域请求和安全响应头
    """
    if hasattr(Config, "CORS_ENABLED") and Config.CORS_ENABLED:
        origin = request.headers.get("Origin", "")
        allowed_origins = getattr(Config, "ALLOWED_ORIGINS", [])
        allow_credentials = False

        if origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            allow_credentials = True
        elif "*" in allowed_origins:
            # 通配符不能与 credentials 同时使用，否则浏览器会拒绝响应
            response.headers["Access-Control-Allow-Origin"] = "*"

        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, DELETE, OPTIONS"
        )
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, Authorization, X-Requested-With"
        )
        if allow_credentials:
            response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Max-Age"] = "3600"

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.proxy.ustclug.org; "
        "font-src 'self' https://fonts.gstatic.com https://fonts.proxy.ustclug.org data:; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'self';"
    )
    if SESSION_COOKIE_SECURE:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

    return response


@app.after_request
def after_request(response):
    return cors_response(response)


@app.route("/healthz")
def healthz():
    """健康检查：用于 Docker HEALTHCHECK 与反向代理探活"""
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1")
        conn.close()
    except Exception:
        logger.exception("健康检查失败")
        return jsonify({"status": "error", "db": "error"}), 503
    return jsonify({"status": "ok", "db": "ok"})


@app.route("/sw.js")
def service_worker():
    """Service Worker 必须从根路径提供，才能控制整个站点"""
    response = send_from_directory(
        app.static_folder, "sw.js", mimetype="application/javascript"
    )
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/api/options", methods=["OPTIONS"])
def handle_options():
    response = jsonify({"status": "ok"})
    return cors_response(response)








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

        # 校验用户仍然存在且会话版本一致：被删除/被重置密码用户的旧会话立即失效
        conn = get_db_connection()
        user = conn.execute(
            "SELECT id, session_version, is_active FROM users WHERE id = ?",
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
            "SELECT is_admin, session_version, is_active FROM users WHERE id = ?",
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

        if user["is_admin"] != 1:
            return jsonify({"error": "需要管理员权限"}), 403

        return f(*args, **kwargs)

    return decorated_function




def get_client_ip():
    """获取客户端 IP，兼容反向代理"""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return (request.remote_addr or "")[:64]


def record_login_attempt(username, success):
    """
    记录一次登录尝试；失败次数达到阈值时写审计日志。
    成功登录会清除该用户的历史失败记录。
    """
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO login_attempts (username, ip, attempted_at, success) VALUES (?, ?, ?, ?)",
            (username, get_client_ip(), now_string(), 1 if success else 0),
        )
        # 只保留一天的记录
        conn.execute(
            "DELETE FROM login_attempts WHERE attempted_at < ?",
            (now_string(datetime.now() - timedelta(days=1)),),
        )

        if success:
            conn.execute(
                "DELETE FROM login_attempts WHERE username = ? AND success = 0",
                (username,),
            )
        else:
            cutoff = now_string(
                datetime.now() - timedelta(seconds=LOGIN_WINDOW_SECONDS)
            )
            failures = conn.execute(
                "SELECT COUNT(*) FROM login_attempts WHERE username = ? AND success = 0 AND attempted_at >= ?",
                (username, cutoff),
            ).fetchone()[0]
            if failures == LOGIN_MAX_FAILURES:
                log_audit(
                    conn,
                    None,
                    "login_locked",
                    "user",
                    None,
                    detail=f"用户名 {username} 连续登录失败 {failures} 次",
                )
        conn.commit()
    finally:
        conn.close()


def login_lock_status(username):
    """
    返回 (是否锁定, 剩余秒数)。
    统计窗口内失败次数达到阈值后，从最后一次失败起锁定 LOGIN_LOCK_SECONDS 秒。
    """
    cutoff = now_string(datetime.now() - timedelta(seconds=LOGIN_WINDOW_SECONDS))
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS failures, MAX(attempted_at) AS last_failure FROM login_attempts WHERE username = ? AND success = 0 AND attempted_at >= ?",
            (username, cutoff),
        ).fetchone()
    finally:
        conn.close()

    if not row or row["failures"] < LOGIN_MAX_FAILURES or not row["last_failure"]:
        return False, 0

    last_failure = datetime.strptime(row["last_failure"], "%Y-%m-%d %H:%M:%S")
    remaining = int(
        (
            last_failure
            + timedelta(seconds=LOGIN_LOCK_SECONDS)
            - datetime.now()
        ).total_seconds()
    )
    if remaining <= 0:
        return False, 0
    return True, remaining












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
    _token_data, error = get_reset_token(token)
    if error:
        return render_template("reset_password.html", error=error), 404

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

    if not reset_request_allowed(user["id"]):
        logger.warning("密码重置请求过于频繁，已跳过发送（user_id=%s）", user["id"])
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

    success = enqueue_email(
        email,
        "待办事项系统 - 密码重置",
        html_content,
        user_id=user["id"],
    )

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

    _token_data, error = get_reset_token(token)
    if error:
        return jsonify({"error": error}), 400

    # 原子消耗令牌并修改密码，同时使该用户所有旧会话失效
    if reset_password_with_token(token, new_password) is None:
        return jsonify({"error": "链接无效或已过期"}), 400

    return jsonify({"message": "密码重置成功"})


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

    locked, remaining = login_lock_status(username)
    if locked:
        minutes = max(1, (remaining + 59) // 60)
        response = jsonify({"error": f"尝试次数过多，请在 {minutes} 分钟后重试"})
        response.headers["Retry-After"] = str(max(1, remaining))
        return response, 429

    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()

    if not user:
        conn.close()
        record_login_attempt(username, False)
        return jsonify({"error": "用户名或密码错误"}), 401

    matched, needs_rehash = verify_password(user["password"], password)
    if not matched:
        conn.close()
        record_login_attempt(username, False)
        return jsonify({"error": "用户名或密码错误"}), 401

    if user["is_active"] == 0:
        conn.close()
        return jsonify({"error": "账户已被禁用，请联系管理员"}), 403

    record_login_attempt(username, True)

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
    session["session_version"] = user["session_version"]

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
        "SELECT email, reminder_time, reminder_enabled, review_enabled, review_time FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()
    conn.close()

    reminder_time = (
        user["reminder_time"] if user and user["reminder_time"] is not None else 540
    )
    review_time = (
        user["review_time"] if user and user["review_time"] is not None else 1200
    )
    reminder_enabled = bool(user["reminder_enabled"]) if user else True
    review_enabled = bool(user["review_enabled"]) if user else False
    reminder_hour = reminder_time // 60
    reminder_minute = reminder_time % 60

    return jsonify(
        {
            "id": session["user_id"],
            "username": session["username"],
            "email": user["email"] if user else None,
            "is_admin": bool(session.get("is_admin", False)),
            "reminder_time": reminder_time,
            "reminder_enabled": reminder_enabled,
            "reminder_hour": reminder_hour,
            "reminder_minute": reminder_minute,
            "review_enabled": review_enabled,
            "review_time": review_time,
            "review_hour": review_time // 60,
            "review_minute": review_time % 60,
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
    reminder_enabled = data.get("reminder_enabled")

    if reminder_hour is None and reminder_enabled is None:
        return jsonify({"error": "请提供提醒时间或开关状态"}), 400

    updates = {}
    if reminder_hour is not None:
        try:
            reminder_hour = int(reminder_hour)
            reminder_minute = (
                int(reminder_minute) if reminder_minute is not None else 0
            )
        except (ValueError, TypeError):
            return jsonify({"error": "请提供有效的提醒时间"}), 400

        if reminder_hour < 0 or reminder_hour > 23:
            return jsonify({"error": "小时必须是0-23之间的整数"}), 400
        if reminder_minute < 0 or reminder_minute > 59:
            return jsonify({"error": "分钟必须是0-59之间的整数"}), 400

        updates["reminder_time"] = reminder_hour * 60 + reminder_minute

    if reminder_enabled is not None:
        if not isinstance(reminder_enabled, bool):
            return jsonify({"error": "reminder_enabled 必须是布尔值"}), 400
        updates["reminder_enabled"] = 1 if reminder_enabled else 0

    conn = get_db_connection()
    assignments = ", ".join(f"{field} = ?" for field in updates)
    conn.execute(
        f"UPDATE users SET {assignments} WHERE id = ?",
        (*updates.values(), session["user_id"]),
    )
    conn.commit()
    user = conn.execute(
        "SELECT reminder_time, reminder_enabled FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()
    conn.close()

    return jsonify(
        {
            "message": "提醒设置已更新",
            "reminder_time": user["reminder_time"],
            "reminder_hour": user["reminder_time"] // 60,
            "reminder_minute": user["reminder_time"] % 60,
            "reminder_enabled": bool(user["reminder_enabled"]),
        }
    )


def _request_token():
    """从 Authorization、查询参数或 JSON 中提取 API 令牌"""
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()

    token = request.args.get("token")
    if token:
        return token.strip()

    data = request.get_json(silent=True)
    if isinstance(data, dict):
        token = data.get("token")
        if isinstance(token, str):
            return token.strip()
    return ""


def authenticate_api_token(token):
    """按 API 令牌查找启用中的用户"""
    if not token:
        return None

    token_hash = hash_reset_token(token)
    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE api_token_hash = ? AND is_active = 1", (token_hash,)
    ).fetchone()
    conn.close()
    return user


@app.route("/api/me/api-token", methods=["GET"])
@login_required
def get_api_token_status():
    conn = get_db_connection()
    user = conn.execute(
        "SELECT api_token_hash, api_token_created_at FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()
    conn.close()

    enabled = bool(user and user["api_token_hash"])
    return jsonify(
        {
            "enabled": enabled,
            "created_at": user["api_token_created_at"] if user else None,
            "capture_url": f"{BASE_URL}/capture" if enabled else None,
        }
    )


@app.route("/api/me/api-token", methods=["POST"])
@login_required
def create_api_token():
    token = secrets.token_urlsafe(32)
    conn = get_db_connection()
    conn.execute(
        "UPDATE users SET api_token_hash = ?, api_token_created_at = ? WHERE id = ?",
        (hash_reset_token(token), now_string(), session["user_id"]),
    )
    log_audit(
        conn, session["user_id"], "create_api_token", "user", session["user_id"]
    )
    conn.commit()
    conn.close()

    return jsonify(
        {
            "token": token,
            "capture_url": f"{BASE_URL}/capture?token={token}",
            "message": "请妥善保存，令牌只显示一次",
        }
    )


@app.route("/api/me/api-token", methods=["DELETE"])
@login_required
def revoke_api_token():
    conn = get_db_connection()
    conn.execute(
        "UPDATE users SET api_token_hash = NULL, api_token_created_at = NULL WHERE id = ?",
        (session["user_id"],),
    )
    log_audit(
        conn, session["user_id"], "revoke_api_token", "user", session["user_id"]
    )
    conn.commit()
    conn.close()

    return jsonify({"message": "API 令牌已撤销"})


@app.route("/api/capture", methods=["POST"])
def capture_todo():
    """使用 API 令牌快速捕获任务（自然语言）"""
    token = _request_token()
    user = authenticate_api_token(token)
    if not user:
        return jsonify({"error": "令牌无效"}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = request.form.to_dict() if request.form else {}

    text = data.get("text") or data.get("title") or ""
    parsed = parse_natural(text)
    if parsed is None:
        return jsonify({"error": "无法解析任务内容"}), 400

    now = datetime.now()
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO todos
            (title, description, user_id, created_date, created_at, due_date, due_time, priority, tags, context, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            parsed["title"],
            data.get("description") or "",
            user["id"],
            now.strftime("%Y-%m-%d"),
            now_string(now),
            parsed["due_date"],
            parsed["due_time"],
            parsed["priority"] or 2,
            json.dumps(parsed["tags"], ensure_ascii=False) if parsed["tags"] else None,
            parsed["context"],
            now_string(now),
        ),
    )
    conn.commit()
    todo_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    todo = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    conn.close()

    return jsonify(serialize_todo(todo)), 201


@app.route("/capture")
def capture_page():
    token = request.args.get("token", "").strip()
    user = authenticate_api_token(token)
    if not user:
        return (
            render_template("capture.html", error="链接无效或令牌已被撤销", token=""),
            403,
        )
    return render_template("capture.html", token=token)


@app.route("/api/me/review", methods=["PUT"])
@login_required
def update_review_settings():
    data = read_json_object()
    if data is None:
        return jsonify({"error": "请求必须是 JSON 对象"}), 400

    updates = {}
    if "review_enabled" in data:
        if not isinstance(data["review_enabled"], bool):
            return jsonify({"error": "review_enabled 必须是布尔值"}), 400
        updates["review_enabled"] = 1 if data["review_enabled"] else 0

    if "review_hour" in data or "review_minute" in data:
        try:
            hour = int(data.get("review_hour", 20))
            minute = int(data.get("review_minute", 0))
        except (TypeError, ValueError):
            return jsonify({"error": "请提供有效的回顾时间"}), 400
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            return jsonify({"error": "回顾时间必须是 0-23 时 / 0-59 分"}), 400
        updates["review_time"] = hour * 60 + minute

    if not updates:
        return jsonify({"error": "没有可更新的回顾设置"}), 400

    conn = get_db_connection()
    assignments = ", ".join(f"{field} = ?" for field in updates)
    conn.execute(
        f"UPDATE users SET {assignments} WHERE id = ?",
        (*updates.values(), session["user_id"]),
    )
    log_audit(conn, session["user_id"], "update_review", "user", session["user_id"])
    conn.commit()
    user = conn.execute(
        "SELECT review_enabled, review_time FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()
    conn.close()

    return jsonify(
        {
            "message": "回顾设置已更新",
            "review_enabled": bool(user["review_enabled"]),
            "review_time": user["review_time"],
            "review_hour": user["review_time"] // 60,
            "review_minute": user["review_time"] % 60,
        }
    )


@app.route("/api/me/review/send", methods=["POST"])
@login_required
def send_review_now():
    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT * FROM users WHERE id = ?", (session["user_id"],)
        ).fetchone()
        if not user["email"]:
            return jsonify({"error": "请先在设置中填写邮箱"}), 400

        now = datetime.now()
        stats = collect_review_stats(conn, user["id"], now)
        todos = conn.execute(
            "SELECT * FROM todos WHERE user_id = ? AND completed = 0 AND deleted_at IS NULL ORDER BY priority DESC, created_at ASC LIMIT 10",
            (user["id"],),
        ).fetchall()
        html = build_daily_review_email(user, stats, todos, now)
        ok = enqueue_email(
            user["email"],
            f"今日回顾 - {now.strftime('%Y-%m-%d')}",
            html,
            user_id=user["id"],
        )
    finally:
        conn.close()

    if not ok:
        return jsonify({"error": "回顾邮件入队失败"}), 500
    return jsonify({"message": "回顾邮件已加入发送队列"})


@app.route("/settings")
def settings_page():
    if "user_id" not in session:
        return redirect("/login")
    return render_template("settings.html")


@app.route("/api/me/password", methods=["PUT"])
@login_required
def change_password():
    data = read_json_object()
    if data is None:
        return jsonify({"error": "请求必须是 JSON 对象"}), 400

    current_password = data.get("current_password")
    if not isinstance(current_password, str) or not current_password:
        return jsonify({"error": "请输入当前密码"}), 400

    new_password, error = validate_password(data.get("new_password"))
    if error:
        return jsonify({"error": error}), 400

    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT id, password FROM users WHERE id = ?", (session["user_id"],)
        ).fetchone()
        matched, _ = verify_password(user["password"], current_password)
        if not matched:
            return jsonify({"error": "当前密码不正确"}), 400

        conn.execute(
            "UPDATE users SET password = ?, session_version = session_version + 1 WHERE id = ?",
            (hash_password(new_password), user["id"]),
        )
        log_audit(conn, user["id"], "change_password", "user", user["id"])
        conn.commit()
    finally:
        conn.close()

    session.clear()
    return jsonify({"message": "密码已修改，请重新登录"})


@app.route("/api/me/email", methods=["PUT"])
@login_required
def change_email():
    data = read_json_object()
    if data is None:
        return jsonify({"error": "请求必须是 JSON 对象"}), 400

    new_email, error = validate_email(data.get("email"))
    if error:
        return jsonify({"error": error}), 400

    current_password = data.get("current_password")
    if not isinstance(current_password, str) or not current_password:
        return jsonify({"error": "请输入当前密码"}), 400

    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT id, password, email FROM users WHERE id = ?",
            (session["user_id"],),
        ).fetchone()
        matched, _ = verify_password(user["password"], current_password)
        if not matched:
            return jsonify({"error": "当前密码不正确"}), 400

        if (user["email"] or "").lower() == new_email:
            return jsonify({"message": "邮箱未变化", "email": new_email})

        duplicate = conn.execute(
            "SELECT id FROM users WHERE LOWER(email) = ? AND id != ?",
            (new_email, user["id"]),
        ).fetchone()
        if duplicate:
            return jsonify({"error": "该邮箱已被其他账户使用"}), 400

        conn.execute(
            "UPDATE users SET email = ? WHERE id = ?", (new_email, user["id"])
        )
        log_audit(conn, user["id"], "change_email", "user", user["id"])
        conn.commit()
    finally:
        conn.close()

    return jsonify({"message": "邮箱已更新", "email": new_email})


@app.route("/api/me/logout-all", methods=["POST"])
@login_required
def logout_all_devices():
    conn = get_db_connection()
    conn.execute(
        "UPDATE users SET session_version = session_version + 1 WHERE id = ?",
        (session["user_id"],),
    )
    log_audit(conn, session["user_id"], "logout_all", "user", session["user_id"])
    conn.commit()
    conn.close()

    session.clear()
    return jsonify({"message": "已退出所有设备，请重新登录"})


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
    支持日期、状态、优先级、关键字、排序与数量限制
    """
    date, error = validate_date(request.args.get("date"), "日期")
    if error:
        return jsonify({"error": error}), 400

    view = request.args.get("view", "today")
    trash = request.args.get("trash") == "1" or view == "trash"
    status = request.args.get("status", "")
    keyword = (request.args.get("q") or "").strip()[:100]
    priority = request.args.get("priority", type=int)
    tag = (request.args.get("tag") or "").strip()[:20]
    context_filter = (request.args.get("context") or "").strip()[:20]
    sort = request.args.get("sort", "created_desc")
    limit = request.args.get("limit", 200, type=int) or 200
    limit = min(max(limit, 1), 500)

    deleted_filter = "deleted_at IS NOT NULL" if trash else "deleted_at IS NULL"
    where = ["user_id = ?", deleted_filter]
    params = [session["user_id"]]

    if date:
        where.append("created_date = ?")
        params.append(date)

    if view == "all":
        completed_filter = None
    elif view == "completed":
        completed_filter = 1
    elif trash:
        completed_filter = None
    else:
        completed_filter = 0

    if status == "active":
        completed_filter = 0
    elif status == "completed":
        completed_filter = 1
    elif status == "all":
        completed_filter = None

    if completed_filter is not None:
        where.append("completed = ?")
        params.append(completed_filter)

    if keyword:
        where.append(
            "(title LIKE ? OR description LIKE ? OR tags LIKE ? OR context LIKE ?)"
        )
        params.extend([f"%{keyword}%"] * 4)

    if tag:
        where.append("tags LIKE ?")
        params.append(f'%"{tag}"%')

    if context_filter:
        where.append("context = ?")
        params.append(context_filter)

    if priority in VALID_PRIORITIES:
        where.append("priority = ?")
        params.append(priority)

    default_order = "deleted_at DESC" if trash else "created_at DESC"
    order_by = {
        "created_desc": "created_at DESC",
        "created_asc": "created_at ASC",
        "due_asc": "CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, due_date ASC, created_at DESC",
        "priority_desc": "priority DESC, created_at DESC",
        "deleted_desc": "deleted_at DESC",
    }.get(sort, default_order)

    sql = f"SELECT * FROM todos WHERE {' AND '.join(where)} ORDER BY {order_by} LIMIT ?"
    params.append(limit)

    conn = get_db_connection()
    todos = conn.execute(sql, params).fetchall()
    conn.close()

    return jsonify([serialize_todo(todo) for todo in todos])


@app.route("/api/todos/stats", methods=["GET"])
@login_required
def get_todo_stats():
    """当前用户的待办统计：未完成、已完成、今日新增、逾期"""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    row = conn.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END) AS pending,
               SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS completed,
               SUM(CASE WHEN completed = 0 AND due_date IS NOT NULL AND due_date < ? THEN 1 ELSE 0 END) AS overdue,
               SUM(CASE WHEN created_date = ? THEN 1 ELSE 0 END) AS created_today,
               SUM(CASE WHEN is_mit = 1 AND mit_date = ? AND completed = 0 THEN 1 ELSE 0 END) AS mit_pending,
               SUM(CASE WHEN is_mit = 1 AND mit_date = ? AND completed = 1 THEN 1 ELSE 0 END) AS mit_completed
        FROM todos WHERE user_id = ? AND deleted_at IS NULL
        """,
        (today, today, today, today, session["user_id"]),
    ).fetchone()
    conn.close()

    return jsonify(
        {
            "total": row["total"] or 0,
            "pending": row["pending"] or 0,
            "completed": row["completed"] or 0,
            "overdue": row["overdue"] or 0,
            "created_today": row["created_today"] or 0,
            "mit_pending": row["mit_pending"] or 0,
            "mit_completed": row["mit_completed"] or 0,
        }
    )


@app.route("/api/todos", methods=["POST"])
@login_required
def add_todo():
    """
    添加待办事项API
    支持自然语言解析（natural=true）与显式字段
    """
    data = read_json_object()
    if data is None:
        return jsonify({"error": "请求必须是 JSON 对象"}), 400

    natural = data.get("natural") is True
    if natural:
        parsed = parse_natural(data.get("title") or "")
        if parsed is None:
            return jsonify({"error": "无法从描述中解析出任务标题"}), 400
        raw_title = parsed["title"]
        raw_due_date = parsed["due_date"]
        raw_due_time = parsed["due_time"]
        raw_priority = parsed["priority"]
        raw_tags = parsed["tags"]
        raw_context = parsed["context"]

        # 显式字段优先于自然语言解析结果
        if data.get("due_date") not in (None, ""):
            raw_due_date = data["due_date"]
        if data.get("due_time") not in (None, ""):
            raw_due_time = data["due_time"]
        if data.get("priority") is not None:
            raw_priority = data["priority"]
        if data.get("tags") is not None:
            raw_tags = data["tags"]
        if data.get("context") not in (None, ""):
            raw_context = data["context"]
    else:
        raw_title = data.get("title")
        raw_due_date = data.get("due_date")
        raw_due_time = data.get("due_time")
        raw_priority = data.get("priority")
        raw_tags = data.get("tags", [])
        raw_context = data.get("context")

    title, error = validate_text(raw_title, "标题", MAX_TODO_TITLE, required=True)
    if error:
        return jsonify({"error": error}), 400

    description, error = validate_text(
        data.get("description"), "描述", MAX_TODO_DESCRIPTION
    )
    if error:
        return jsonify({"error": error}), 400

    due_date, error = validate_date(raw_due_date, "截止日期")
    if error:
        return jsonify({"error": error}), 400

    due_time, error = validate_time(raw_due_time, "截止时间")
    if error:
        return jsonify({"error": error}), 400

    priority, error = validate_priority(raw_priority)
    if error:
        return jsonify({"error": error}), 400

    tags, error = validate_tags(raw_tags)
    if error:
        return jsonify({"error": error}), 400

    context, error = validate_context(raw_context)
    if error:
        return jsonify({"error": error}), 400

    user_id = session["user_id"]

    now = datetime.now()
    created_date = now.strftime("%Y-%m-%d")
    created_at = now_string(now)

    conn = get_db_connection()
    cursor = conn.execute(
        """
        INSERT INTO todos
            (title, description, user_id, created_date, created_at, due_date, due_time, priority, tags, context, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            description,
            user_id,
            created_date,
            created_at,
            due_date,
            due_time,
            priority,
            json.dumps(tags, ensure_ascii=False) if tags else None,
            context,
            created_at,
        ),
    )
    conn.commit()
    todo_id = cursor.lastrowid
    todo = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    conn.close()

    return jsonify(serialize_todo(todo)), 201


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
        "SELECT * FROM todos WHERE id = ? AND user_id = ? AND deleted_at IS NULL",
        (todo_id, user_id),
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
        updates["completed_at"] = now_string() if data["completed"] else None

    if "due_date" in data:
        due_date, error = validate_date(data["due_date"], "截止日期")
        if error:
            conn.close()
            return jsonify({"error": error}), 400
        updates["due_date"] = due_date
        if not due_date and "due_time" not in data:
            updates["due_time"] = None

    if "due_time" in data:
        due_time, error = validate_time(data["due_time"], "截止时间")
        if error:
            conn.close()
            return jsonify({"error": error}), 400
        updates["due_time"] = due_time

    if "tags" in data:
        tags, error = validate_tags(data["tags"])
        if error:
            conn.close()
            return jsonify({"error": error}), 400
        updates["tags"] = json.dumps(tags, ensure_ascii=False) if tags else None

    if "context" in data:
        context, error = validate_context(data["context"])
        if error:
            conn.close()
            return jsonify({"error": error}), 400
        updates["context"] = context

    if "priority" in data:
        priority, error = validate_priority(data["priority"])
        if error:
            conn.close()
            return jsonify({"error": error}), 400
        updates["priority"] = priority

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
        updates["updated_at"] = now_string()
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

    return jsonify(serialize_todo(updated_todo))


@app.route("/api/todos/mit", methods=["GET"])
@login_required
def get_mit_todos():
    """今天的“三件最重要的事”"""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    todos = conn.execute(
        """
        SELECT * FROM todos
        WHERE user_id = ? AND is_mit = 1 AND mit_date = ? AND deleted_at IS NULL
        ORDER BY completed ASC, priority DESC, created_at DESC
        """,
        (session["user_id"], today),
    ).fetchall()
    conn.close()
    return jsonify([serialize_todo(todo) for todo in todos])


@app.route("/api/todos/<int:todo_id>/mit", methods=["PUT"])
@login_required
def toggle_mit(todo_id):
    """设置/取消今日三件事，每个用户每天最多 3 项"""
    data = read_json_object()
    if data is None:
        return jsonify({"error": "请求必须是 JSON 对象"}), 400

    is_mit = data.get("is_mit")
    if not isinstance(is_mit, bool):
        return jsonify({"error": "is_mit 必须是布尔值"}), 400

    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    try:
        todo = conn.execute(
            "SELECT * FROM todos WHERE id = ? AND user_id = ? AND deleted_at IS NULL",
            (todo_id, session["user_id"]),
        ).fetchone()
        if not todo:
            return jsonify({"error": "待办事项不存在"}), 404

        if is_mit:
            already = todo["is_mit"] == 1 and todo["mit_date"] == today
            if not already:
                count = conn.execute(
                    "SELECT COUNT(*) FROM todos WHERE user_id = ? AND is_mit = 1 AND mit_date = ? AND deleted_at IS NULL",
                    (session["user_id"], today),
                ).fetchone()[0]
                if count >= 3:
                    return jsonify({"error": "今日三件事最多选择 3 项"}), 400
            conn.execute(
                "UPDATE todos SET is_mit = 1, mit_date = ?, updated_at = ? WHERE id = ?",
                (today, now_string(), todo_id),
            )
        else:
            conn.execute(
                "UPDATE todos SET is_mit = 0, mit_date = NULL, updated_at = ? WHERE id = ?",
                (now_string(), todo_id),
            )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM todos WHERE id = ?", (todo_id,)
        ).fetchone()
    finally:
        conn.close()

    return jsonify(serialize_todo(updated))


@app.route("/api/todos/<int:todo_id>", methods=["DELETE"])
@login_required
def delete_todo(todo_id):
    """把待办移入回收站（软删除）"""
    now = now_string()
    conn = get_db_connection()
    cursor = conn.execute(
        "UPDATE todos SET deleted_at = ?, updated_at = ? WHERE id = ? AND user_id = ? AND deleted_at IS NULL",
        (now, now, todo_id, session["user_id"]),
    )
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        return jsonify({"error": "待办事项不存在"}), 404

    return jsonify({"message": "已移入回收站"})


@app.route("/api/todos/<int:todo_id>/restore", methods=["POST"])
@login_required
def restore_todo(todo_id):
    """从回收站恢复待办"""
    conn = get_db_connection()
    cursor = conn.execute(
        "UPDATE todos SET deleted_at = NULL, updated_at = ? WHERE id = ? AND user_id = ? AND deleted_at IS NOT NULL",
        (now_string(), todo_id, session["user_id"]),
    )
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        return jsonify({"error": "待办事项不在回收站中"}), 404

    return jsonify({"message": "已恢复"})


@app.route("/api/todos/<int:todo_id>/purge", methods=["DELETE"])
@login_required
def purge_todo(todo_id):
    """从回收站彻底删除"""
    conn = get_db_connection()
    cursor = conn.execute(
        "DELETE FROM todos WHERE id = ? AND user_id = ? AND deleted_at IS NOT NULL",
        (todo_id, session["user_id"]),
    )
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        return jsonify({"error": "待办事项不在回收站中"}), 404

    return jsonify({"message": "已彻底删除"})


def parse_todo_ids(values):
    """校验批量操作 ID 列表"""
    if not isinstance(values, list) or not values or len(values) > 200:
        return None

    ids = []
    for value in values:
        if isinstance(value, bool):
            return None
        try:
            todo_id = int(value)
        except (TypeError, ValueError):
            return None
        if todo_id <= 0:
            return None
        ids.append(todo_id)
    return ids


@app.route("/api/todos/batch", methods=["POST"])
@login_required
def batch_todos():
    """批量完成/删除/恢复/彻底删除/修改优先级/截止日期"""
    data = read_json_object()
    if data is None:
        return jsonify({"error": "请求必须是 JSON 对象"}), 400

    ids = parse_todo_ids(data.get("ids"))
    if not ids:
        return jsonify({"error": "ids 必须是非空数组，最多 200 项"}), 400

    action = data.get("action")
    now = now_string()
    placeholders = ", ".join("?" for _ in ids)
    user_id = session["user_id"]

    if action == "complete":
        sql = f"UPDATE todos SET completed = 1, completed_at = ?, updated_at = ? WHERE user_id = ? AND deleted_at IS NULL AND id IN ({placeholders})"
        params = [now, now, user_id, *ids]
    elif action == "uncomplete":
        sql = f"UPDATE todos SET completed = 0, completed_at = NULL, updated_at = ? WHERE user_id = ? AND deleted_at IS NULL AND id IN ({placeholders})"
        params = [now, user_id, *ids]
    elif action == "delete":
        sql = f"UPDATE todos SET deleted_at = ?, updated_at = ? WHERE user_id = ? AND deleted_at IS NULL AND id IN ({placeholders})"
        params = [now, now, user_id, *ids]
    elif action == "restore":
        sql = f"UPDATE todos SET deleted_at = NULL, updated_at = ? WHERE user_id = ? AND deleted_at IS NOT NULL AND id IN ({placeholders})"
        params = [now, user_id, *ids]
    elif action == "purge":
        sql = f"DELETE FROM todos WHERE user_id = ? AND deleted_at IS NOT NULL AND id IN ({placeholders})"
        params = [user_id, *ids]
    elif action == "priority":
        priority, error = validate_priority(data.get("priority"))
        if error:
            return jsonify({"error": error}), 400
        sql = f"UPDATE todos SET priority = ?, updated_at = ? WHERE user_id = ? AND deleted_at IS NULL AND id IN ({placeholders})"
        params = [priority, now, user_id, *ids]
    elif action == "due_date":
        due_date, error = validate_date(data.get("due_date"), "截止日期")
        if error:
            return jsonify({"error": error}), 400
        sql = f"UPDATE todos SET due_date = ?, updated_at = ? WHERE user_id = ? AND deleted_at IS NULL AND id IN ({placeholders})"
        params = [due_date, now, user_id, *ids]
    else:
        return jsonify({"error": "不支持的批量操作"}), 400

    conn = get_db_connection()
    cursor = conn.execute(sql, params)
    conn.commit()
    conn.close()

    return jsonify({"message": "批量操作完成", "updated": cursor.rowcount})


def csv_safe(value):
    """避免 CSV 公式注入"""
    text = "" if value is None else str(value)
    if text and text[0] in ("=", "+", "-", "@"):
        return "'" + text
    return text


@app.route("/api/todos/export", methods=["GET"])
@login_required
def export_todos():
    """导出当前用户未删除的待办（CSV/JSON）"""
    fmt = (request.args.get("format") or "csv").lower()
    if fmt not in ("csv", "json"):
        return jsonify({"error": "format 只支持 csv 或 json"}), 400

    conn = get_db_connection()
    todos = conn.execute(
        "SELECT * FROM todos WHERE user_id = ? AND deleted_at IS NULL ORDER BY created_at DESC",
        (session["user_id"],),
    ).fetchall()
    conn.close()

    rows = [serialize_todo(todo) for todo in todos]
    filename = f"todos-{datetime.now().strftime('%Y%m%d')}.{fmt}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    if fmt == "json":
        return Response(
            json.dumps(rows, ensure_ascii=False, indent=2),
            mimetype="application/json",
            headers=headers,
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["id", "标题", "描述", "完成", "优先级", "截止日期", "创建时间", "完成时间"]
    )
    for row in rows:
        writer.writerow(
            [
                row["id"],
                csv_safe(row["title"]),
                csv_safe(row["description"]),
                "是" if row["completed"] else "否",
                row["priority"],
                row["due_date"] or "",
                row["created_at"] or "",
                row["completed_at"] or "",
            ]
        )

    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv",
        headers=headers,
    )


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


@app.route("/api/admin/stats", methods=["GET"])
@admin_required
def admin_stats():
    """管理后台概览数据"""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    users_total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    admins = conn.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1").fetchone()[0]
    disabled = conn.execute("SELECT COUNT(*) FROM users WHERE is_active = 0").fetchone()[0]
    active_users = conn.execute(
        "SELECT COUNT(*) FROM users WHERE last_login_at >= ?", (week_ago,)
    ).fetchone()[0]
    todos_total = conn.execute(
        "SELECT COUNT(*) FROM todos WHERE deleted_at IS NULL"
    ).fetchone()[0]
    todos_pending = conn.execute(
        "SELECT COUNT(*) FROM todos WHERE completed = 0 AND deleted_at IS NULL"
    ).fetchone()[0]
    todos_today = conn.execute(
        "SELECT COUNT(*) FROM todos WHERE created_date = ? AND deleted_at IS NULL",
        (today,),
    ).fetchone()[0]
    todos_overdue = conn.execute(
        "SELECT COUNT(*) FROM todos WHERE completed = 0 AND deleted_at IS NULL AND due_date IS NOT NULL AND due_date < ?",
        (today,),
    ).fetchone()[0]
    emails_pending = conn.execute(
        "SELECT COUNT(*) FROM email_outbox WHERE status = 'pending'"
    ).fetchone()[0]
    emails_failed = conn.execute(
        "SELECT COUNT(*) FROM email_outbox WHERE status = 'failed'"
    ).fetchone()[0]
    conn.close()

    completion_rate = (
        round((todos_total - todos_pending) * 100 / todos_total, 1)
        if todos_total
        else 0.0
    )

    return jsonify(
        {
            "users_total": users_total,
            "admins": admins,
            "disabled": disabled,
            "active_users": active_users,
            "todos_total": todos_total,
            "todos_pending": todos_pending,
            "todos_today": todos_today,
            "todos_overdue": todos_overdue,
            "emails_pending": emails_pending,
            "emails_failed": emails_failed,
            "completion_rate": completion_rate,
        }
    )


@app.route("/api/admin/audit-logs", methods=["GET"])
@admin_required
def get_audit_logs():
    limit = request.args.get("limit", 20, type=int) or 20
    limit = min(max(limit, 1), 100)

    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT a.id, a.action, a.target_type, a.target_id, a.detail, a.created_at,
               u.username AS actor_name
        FROM audit_logs a
        LEFT JOIN users u ON u.id = a.actor_id
        ORDER BY a.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()

    return jsonify(
        [
            {
                "id": row["id"],
                "action": row["action"],
                "actor_name": row["actor_name"] or "系统",
                "target_type": row["target_type"],
                "target_id": row["target_id"],
                "detail": row["detail"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    )


@app.route("/api/admin/emails", methods=["GET"])
@admin_required
def get_outbox_emails():
    """查看邮件发送队列"""
    status = request.args.get("status", "failed")
    if status not in ("pending", "sent", "failed", "all"):
        return jsonify({"error": "status 只支持 pending/sent/failed/all"}), 400

    limit = request.args.get("limit", 20, type=int) or 20
    limit = min(max(limit, 1), 100)

    columns = "id, user_id, to_email, subject, status, attempts, next_attempt_at, last_error, created_at, sent_at"
    conn = get_db_connection()
    try:
        if status == "all":
            rows = conn.execute(
                f"SELECT {columns} FROM email_outbox ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {columns} FROM email_outbox WHERE status = ? ORDER BY id DESC LIMIT ?",
                (status, limit),
            ).fetchall()
    finally:
        conn.close()

    return jsonify([dict(row) for row in rows])


@app.route("/api/admin/emails/<int:email_id>/retry", methods=["POST"])
@admin_required
def retry_email(email_id):
    """把失败邮件重新加入发送队列"""
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            "UPDATE email_outbox SET status = 'pending', attempts = 0, next_attempt_at = ?, last_error = NULL WHERE id = ?",
            (now_string(), email_id),
        )
        if cursor.rowcount == 0:
            return jsonify({"error": "邮件不存在"}), 404
        log_audit(conn, session["user_id"], "retry_email", "email", email_id)
        conn.commit()
    finally:
        conn.close()

    return jsonify({"message": "已重新加入发送队列"})


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

    cutoff = now_string(datetime.now() - timedelta(seconds=LOGIN_WINDOW_SECONDS))
    locked_rows = conn.execute(
        "SELECT username, COUNT(*) AS failures FROM login_attempts WHERE success = 0 AND attempted_at >= ? GROUP BY username HAVING COUNT(*) >= ?",
        (cutoff, LOGIN_MAX_FAILURES),
    ).fetchall()
    locked_usernames = {row["username"] for row in locked_rows}
    conn.close()

    result = []
    for user in users:
        result.append(
            {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "is_admin": bool(user["is_admin"]),
                "is_active": bool(user["is_active"]),
                "locked": user["username"] in locked_usernames,
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
        "SELECT * FROM todos WHERE user_id = ? AND deleted_at IS NULL ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()

    todo_list = [serialize_todo(todo) for todo in todos]

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
        user_id = cursor.lastrowid
        log_audit(conn, session["user_id"], "create_user", "user", user_id)
        conn.commit()
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
            "UPDATE users SET password = ?, session_version = session_version + 1 WHERE id = ?",
            (hashed_password, user_id),
        )
        log_audit(conn, session["user_id"], "reset_password", "user", user_id)
        conn.commit()
        conn.close()

        return jsonify({"message": f"用户 {user['username']} 的密码已重置"})
    except Exception:
        conn.close()
        logger.exception("重置用户密码失败")
        return jsonify({"error": "重置密码失败"}), 500


@app.route("/api/admin/users/<int:user_id>/unlock", methods=["POST"])
@admin_required
def unlock_user(user_id):
    """清除用户近期的登录失败记录，解除锁定"""
    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT username FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            return jsonify({"error": "用户不存在"}), 404

        conn.execute(
            "DELETE FROM login_attempts WHERE username = ? AND success = 0",
            (user["username"],),
        )
        log_audit(conn, session["user_id"], "unlock_user", "user", user_id)
        conn.commit()
    finally:
        conn.close()

    return jsonify({"message": "已解除登录锁定"})


@app.route("/api/admin/users/<int:user_id>", methods=["PUT"])
@admin_required
def update_user(user_id):
    data = read_json_object()
    if data is None:
        return jsonify({"error": "请求必须是 JSON 对象"}), 400

    conn = get_db_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return jsonify({"error": "用户不存在"}), 404

        updates = {}

        if "username" in data:
            username, error = validate_username(data.get("username"))
            if error:
                return jsonify({"error": error}), 400
            duplicate = conn.execute(
                "SELECT id FROM users WHERE LOWER(username) = LOWER(?) AND id != ?",
                (username, user_id),
            ).fetchone()
            if duplicate:
                return jsonify({"error": "用户名已存在"}), 400
            updates["username"] = username

        if "email" in data:
            email, error = validate_email(data.get("email"))
            if error:
                return jsonify({"error": error}), 400
            duplicate = conn.execute(
                "SELECT id FROM users WHERE LOWER(email) = ? AND id != ?",
                (email, user_id),
            ).fetchone()
            if duplicate:
                return jsonify({"error": "邮箱已被注册"}), 400
            updates["email"] = email

        if "is_admin" in data:
            is_admin = data["is_admin"]
            if not isinstance(is_admin, bool):
                return jsonify({"error": "is_admin 必须是布尔值"}), 400
            if user_id == session["user_id"] and not is_admin:
                return jsonify({"error": "不能取消自己的管理员权限"}), 400
            updates["is_admin"] = 1 if is_admin else 0

        if "is_active" in data:
            is_active = data["is_active"]
            if not isinstance(is_active, bool):
                return jsonify({"error": "is_active 必须是布尔值"}), 400
            if user_id == session["user_id"] and not is_active:
                return jsonify({"error": "不能禁用自己的账户"}), 400
            updates["is_active"] = 1 if is_active else 0
            if not is_active:
                updates["session_version"] = (user["session_version"] or 0) + 1

        if not updates:
            return jsonify({"error": "没有可更新的字段"}), 400

        assignments = ", ".join(f"{field} = ?" for field in updates)
        conn.execute(
            f"UPDATE users SET {assignments} WHERE id = ?",
            (*updates.values(), user_id),
        )
        log_audit(
            conn,
            session["user_id"],
            "update_user",
            "user",
            user_id,
            detail="更新字段: " + ", ".join(sorted(updates)),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"message": "用户信息已更新"})


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

        # 先删关联数据再删用户：兼容历史数据库（外键可能未启用级联）
        conn.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM password_reset_requests WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM email_outbox WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM todos WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        log_audit(conn, session["user_id"], "delete_user", "user", user_id)
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
        "SELECT * FROM todos WHERE user_id = ? AND deleted_at IS NULL ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()

    return jsonify([serialize_todo(todo) for todo in todos])


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
    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?", (session["user_id"],)
    ).fetchone()
    conn.close()

    ok, message, status = send_manual_reminder(user)
    if not ok:
        return jsonify({"error": message}), status
    return jsonify({"message": message})


if __name__ == "__main__":
    init_db()
    validate_config(strict=False)

    debug = os.environ.get("FLASK_DEBUG", "1").lower() in ("1", "true")
    # Werkzeug reloader 会启动父子两个进程，只在真正的工作进程里启动调度器
    if not debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_reminder_scheduler()

    app.run(debug=debug, host="0.0.0.0", port=5145)
