"""
配置文件
用于管理应用的环境变量和系统配置
"""

import os


class Config:
    # Flask 应用密钥，用于会话加密
    SECRET_KEY = os.environ.get(
        "SECRET_KEY", "your-secret-key-change-this-in-production"
    )

    # ==================== CORS 跨域配置 ====================
    # 是否启用跨域
    CORS_ENABLED = os.environ.get("CORS_ENABLED", "True").lower() in ["true", "1", "t"]
    # 允许访问的域名列表，多个用逗号分隔
    ALLOWED_ORIGINS = os.environ.get(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:5145,http://127.0.0.1:3000,http://127.0.0.1:5145",
    ).split(",")

    # ==================== 邮件服务配置 ====================
    # SMTP 服务器地址
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.qq.com")
    # SMTP 端口
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    # 是否使用 STARTTLS 加密（587 端口通常为 True）
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() in ["true", "1", "t"]
    # 是否使用 SSL 直连（465 端口通常为 True）
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "False").lower() in [
        "true",
        "1",
        "t",
    ]
    # 连接与读写超时（秒），避免邮件服务器无响应时阻塞请求线程
    MAIL_TIMEOUT = int(os.environ.get("MAIL_TIMEOUT", 15))
    # 邮箱账号
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    # 邮箱密码/授权码
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    # 默认发件人
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@todoapp.com")
    # 是否启用邮件服务
    MAIL_ENABLED = os.environ.get("MAIL_ENABLED", "True").lower() in ["true", "1", "t"]
    # 兼容旧配置：默认提醒小时（新版本按用户 reminder_time 发送）
    MAIL_REMINDER_HOUR = int(os.environ.get("MAIL_REMINDER_HOUR", 0))

    # ==================== 站点配置 ====================
    # 对外访问地址，用于邮件中的链接，例如 https://todo.example.com
    BASE_URL = os.environ.get("BASE_URL", "http://localhost:5145").rstrip("/")
