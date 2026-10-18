"""邮件发送与邮件模板。"""

import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from html import escape as html_escape

from config import Config

logger = logging.getLogger(__name__)


def format_time_ago(created_at_str):
    """格式化时间差，显示已过去多久。"""
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
    except (TypeError, ValueError):
        return "未知"


def send_email(to_email, subject, html_content):
    """
    发送邮件。
    :param to_email: 收件人邮箱
    :param subject: 邮件主题
    :param html_content: 邮件 HTML 内容
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


def build_reminder_email(user, todos, now=None):
    """构建每日提醒邮件，所有用户输入均已转义。"""
    now = now or datetime.now()
    todo_items_html = ""
    for todo in todos:
        created_at = todo["created_at"]
        todo_items_html += f"""
        <div class="todo-item">
            <div class="todo-title">{html_escape(todo["title"])}</div>
            <div class="todo-meta">
                <span class="todo-date">创建于: {html_escape(str(created_at or ""))}</span>
                <span class="time-ago">已过去: {format_time_ago(created_at)}</span>
            </div>
        </div>
        """

    reminder_time = user["reminder_time"] or 540
    reminder_hour = reminder_time // 60
    reminder_minute = reminder_time % 60

    return f"""
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
                <p class="greeting">你好，{html_escape(user["username"])}！</p>
                <div class="notification-time">
                    ⏰ 当前时间: {now.strftime("%Y-%m-%d %H:%M")} | 每日提醒: {reminder_hour:02d}:{reminder_minute:02d}
                </div>
                <p>您共有 <strong>{len(todos)}</strong> 个待办事项未完成：</p>
                <div class="todo-list">
                    {todo_items_html}
                </div>
                <p style="margin-top: 20px;">点击 <a href="{Config.BASE_URL}">这里</a> 查看和管理您的待办事项。</p>
                <p style="color: #999; font-size: 12px;">可以在 <a href="{Config.BASE_URL}/settings">设置页</a> 调整提醒时间或关闭每日提醒。</p>
            </div>
            <div class="footer">
                <p>此邮件由系统自动发送，请勿回复。</p>
            </div>
        </div>
    </body>
    </html>
    """
