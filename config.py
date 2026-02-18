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
    # 是否使用 TLS 加密
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() in ["true", "1", "t"]
    # 邮箱账号
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    # 邮箱密码/授权码
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    # 默认发件人
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@todoapp.com")
    # 是否启用邮件服务
    MAIL_ENABLED = os.environ.get("MAIL_ENABLED", "True").lower() in ["true", "1", "t"]
    # 提醒时间（小时）
    MAIL_REMINDER_HOUR = int(os.environ.get("MAIL_REMINDER_HOUR", 0))
