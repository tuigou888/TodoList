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


def _review_shell(title, body, footer):
    return f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #C4664A 0%, #E08A6C 100%); color: white; padding: 28px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 26px; border-radius: 0 0 10px 10px; }}
            .stats {{ display: flex; gap: 10px; margin: 16px 0; }}
            .stat {{ flex: 1; background: white; border-radius: 8px; padding: 12px; text-align: center; }}
            .stat strong {{ display: block; font-size: 22px; color: #C4664A; }}
            .todo-item {{ background: white; border-radius: 8px; padding: 10px 14px; margin-bottom: 8px; }}
            .todo-title {{ font-weight: 600; }}
            .todo-meta {{ font-size: 12px; color: #888; margin-top: 4px; }}
            .footer {{ text-align: center; color: #999; margin-top: 20px; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header"><h1>{html_escape(title)}</h1></div>
            <div class="content">
                {body}
                {footer}
            </div>
            <div class="footer"><p>此邮件由系统自动发送，请勿回复。</p></div>
        </div>
    </body>
    </html>
    """


def _todo_items_html(todos):
    return "".join(
        f'<div class="todo-item"><div class="todo-title">{html_escape(todo["title"])}</div>'
        f'<div class="todo-meta">优先级 {todo["priority"]}'
        + (f' · 截止 {html_escape(todo["due_date"])}' if todo["due_date"] else "")
        + "</div></div>"
        for todo in todos
    )


def build_daily_review_email(user, stats, todos, now=None):
    """每日回顾邮件。"""
    now = now or datetime.now()
    if stats.get("mit_total"):
        mit_line = (
            f"今日三件事完成 <strong>{stats['mit_completed']}/{stats['mit_total']}</strong>"
        )
    else:
        mit_line = "今日还没有设置三件事，可以在首页用 ☆ 选出最重要的 3 项。"

    body = f"""
        <p>{html_escape(user["username"])}，这是 {now.strftime("%Y-%m-%d")} 的回顾。</p>
        <div class="stats">
            <div class="stat"><strong>{stats["completed_today"]}</strong>今日完成</div>
            <div class="stat"><strong>{stats["pending"]}</strong>未完成</div>
            <div class="stat"><strong>{stats["overdue"]}</strong>已逾期</div>
        </div>
        <p>{mit_line}</p>
        <h3>接下来要做的</h3>
        {_todo_items_html(todos) or "<p>没有未完成的待办，休息一下吧。</p>"}
    """
    footer = f'<p style="margin-top:20px;">前往 <a href="{Config.BASE_URL}">待办事项</a> 或 <a href="{Config.BASE_URL}/settings">设置</a> 调整回顾时间。</p>'
    return _review_shell("每日回顾", body, footer)


def build_weekly_review_email(user, stats, todos, now=None):
    """每周回顾邮件。"""
    now = now or datetime.now()
    oldest = ""
    if stats.get("oldest_title"):
        oldest = (
            f'<p>最久未完成：<strong>{html_escape(stats["oldest_title"])}</strong>'
            f'（创建于 {html_escape(stats["oldest_created_at"] or "")}）</p>'
        )

    body = f"""
        <p>{html_escape(user["username"])}，这是本周的回顾。</p>
        <div class="stats">
            <div class="stat"><strong>{stats["week_completed"]}</strong>本周完成</div>
            <div class="stat"><strong>{stats["week_created"]}</strong>本周新增</div>
            <div class="stat"><strong>{stats["completion_rate"]}%</strong>完成率</div>
        </div>
        <p>当前未完成 <strong>{stats["pending"]}</strong> 项，逾期 <strong>{stats["overdue"]}</strong> 项。</p>
        {oldest}
        <h3>本周重点</h3>
        {_todo_items_html(todos) or "<p>本周没有待办记录。</p>"}
    """
    footer = f'<p style="margin-top:20px;">前往 <a href="{Config.BASE_URL}">待办事项</a> 查看全部任务。</p>'
    return _review_shell("每周回顾", body, footer)
