"""输入校验、请求解析与待办序列化。"""

import json
import re
from datetime import datetime

from flask import request

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fa5-]{3,32}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_TODO_TITLE = 200
MAX_TODO_DESCRIPTION = 2000
VALID_PRIORITIES = (1, 2, 3)
PRIORITY_LABELS = {1: "低", 2: "普通", 3: "高"}


def normalize_email(email):
    """邮箱统一小写存储与查询，避免大小写导致重复账号。"""
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


def validate_date(value, field_name="日期"):
    if value in (None, ""):
        return None, None
    if not isinstance(value, str):
        return None, f"{field_name}格式必须为 YYYY-MM-DD"
    value = value.strip()
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None, f"{field_name}格式必须为 YYYY-MM-DD"
    return value, None


def validate_priority(value):
    if value is None or value == "":
        return 2, None
    try:
        priority = int(value)
    except (TypeError, ValueError):
        return None, "优先级必须是 1-3 的整数"
    if priority not in VALID_PRIORITIES:
        return None, "优先级必须是 1-3 的整数"
    return priority, None


def validate_time(value, field_name="时间"):
    if value in (None, ""):
        return None, None
    if not isinstance(value, str):
        return None, f"{field_name}格式必须为 HH:MM"
    value = value.strip()
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        return None, f"{field_name}格式必须为 HH:MM"
    return value, None


def validate_tags(value):
    if value is None:
        return [], None
    if not isinstance(value, list):
        return None, "tags 必须是数组"
    tags = []
    for item in value[:5]:
        if not isinstance(item, str):
            return None, "标签必须是文本"
        tag = item.strip()[:20]
        if tag and tag not in tags:
            tags.append(tag)
    return tags, None


def validate_context(value):
    if value in (None, ""):
        return None, None
    if not isinstance(value, str):
        return None, "context 必须是文本"
    return value.strip()[:20] or None, None


def _parse_tags(raw):
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()][:5]


def serialize_todo(todo):
    """统一的待办事项输出结构。"""
    return {
        "id": todo["id"],
        "title": todo["title"],
        "description": todo["description"],
        "completed": bool(todo["completed"]),
        "priority": todo["priority"] if todo["priority"] is not None else 2,
        "due_date": todo["due_date"],
        "due_time": todo["due_time"],
        "tags": _parse_tags(todo["tags"]),
        "context": todo["context"],
        "is_mit": bool(todo["is_mit"]),
        "mit_date": todo["mit_date"],
        "created_date": todo["created_date"],
        "created_at": todo["created_at"],
        "completed_at": todo["completed_at"],
        "updated_at": todo["updated_at"],
        "deleted_at": todo["deleted_at"],
    }


def read_json_object():
    """读取 JSON 请求体；非对象或格式错误时返回 None，由调用方返回 400。"""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None
