"""本地自然语言解析：日期、时间、优先级、标签与上下文。

不依赖任何外部服务或 AI，纯规则解析，适合自托管/隐私场景。
示例：
    明天下午3点 交报告 !高 #工作 @电脑
    下周一 10:30 开会 !2 #工作
    10月20日 买牛奶 #生活
"""

import re
from datetime import date, timedelta

WEEKDAY_NAMES = {
    "一": 0,
    "二": 1,
    "三": 2,
    "四": 3,
    "五": 4,
    "六": 5,
    "日": 6,
    "天": 6,
}
CN_DIGITS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
PRIORITY_WORDS = {"高": 3, "紧急": 3, "中": 2, "普通": 2, "低": 1}
PRIORITY_NUMBERS = {"1": 1, "2": 2, "3": 3}

TAG_RE = re.compile(r"[#＃]([^\s#＃!！@＠]{1,20})")
CONTEXT_RE = re.compile(r"[@＠]([^\s#＃!！@＠]{1,20})")
PRIORITY_RE = re.compile(r"[!！]\s*(高|紧急|中|普通|低|[123])")
BANG_RE = re.compile(r"[!！]{2,}")
TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)")
CLOCK_RE = re.compile(
    r"(上午|中午|下午|晚上|早上|凌晨)?\s*"
    r"([0-9]{1,2}|[零一二三四五六七八九十]{1,3})\s*[点时]"
    r"(半|[0-9]{1,2}分?)?"
)
TAG_TRIM = " ,，.。;；:：)）]】"


def _cn_number(value):
    """把中文/阿拉伯数字转换为整数。"""
    value = (value or "").strip()
    if value.isdigit():
        return int(value)
    if value == "十":
        return 10
    if value.startswith("十"):
        return 10 + sum(CN_DIGITS.get(ch, 0) for ch in value[1:])
    if "十" in value:
        left, right = value.split("十", 1)
        tens = CN_DIGITS.get(left, 0)
        ones = sum(CN_DIGITS.get(ch, 0) for ch in right)
        return tens * 10 + ones
    return CN_DIGITS.get(value, 0)


def _consume(pattern, text):
    match = re.search(pattern, text)
    if not match:
        return None, text
    return match, text[: match.start()] + " " + text[match.end() :]


def _parse_priority(text):
    match, rest = _consume(BANG_RE, text)
    if match:
        return max(1, min(len(match.group(0)), 3)), rest

    match, rest = _consume(PRIORITY_RE, text)
    if match:
        key = match.group(1)
        value = PRIORITY_WORDS.get(key) or PRIORITY_NUMBERS.get(key)
        return value, rest

    return None, text


def _parse_date(text, today):
    for word, days in (("大后天", 3), ("后天", 2), ("明天", 1), ("今天", 0)):
        if word in text:
            return today + timedelta(days=days), text.replace(word, " ", 1)

    match, rest = _consume(r"下(?:周|星期|礼拜)([一二三四五六日天])", text)
    if match:
        target = WEEKDAY_NAMES[match.group(1)]
        days = (7 - today.weekday()) + target
        return today + timedelta(days=days), rest

    match, rest = _consume(r"(?:周|星期|礼拜)([一二三四五六日天])", text)
    if match:
        target = WEEKDAY_NAMES[match.group(1)]
        days = (target - today.weekday()) % 7
        if days == 0:
            days = 7
        return today + timedelta(days=days), rest

    match, rest = _consume(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if match:
        try:
            return (
                date(int(match.group(1)), int(match.group(2)), int(match.group(3))),
                rest,
            )
        except ValueError:
            return None, text

    match, rest = _consume(r"(\d{1,2})月(\d{1,2})[日号]", text)
    if match:
        try:
            parsed = date(today.year, int(match.group(1)), int(match.group(2)))
            if parsed < today:
                parsed = date(today.year + 1, parsed.month, parsed.day)
            return parsed, rest
        except ValueError:
            return None, text

    match, rest = _consume(r"(?<!\d)(\d{1,2})[-/](\d{1,2})(?!\d)", text)
    if match:
        try:
            parsed = date(today.year, int(match.group(1)), int(match.group(2)))
            if parsed < today:
                parsed = date(today.year + 1, parsed.month, parsed.day)
            return parsed, rest
        except ValueError:
            return None, text

    return None, text


def _parse_time(text):
    match, rest = _consume(TIME_RE, text)
    if match:
        return int(match.group(1)), int(match.group(2)), rest

    match, rest = _consume(CLOCK_RE, text)
    if not match:
        return None, None, text

    period = match.group(1) or ""
    hour = _cn_number(match.group(2))
    if hour > 23:
        return None, None, text

    suffix = match.group(3) or ""
    if suffix == "半":
        minute = 30
    elif suffix:
        minute = int(re.sub(r"\D", "", suffix) or 0)
    else:
        minute = 0
    if minute > 59:
        minute = 0

    if period in ("下午", "晚上") and hour < 12:
        hour += 12
    elif period == "中午" and hour < 12:
        hour = 12
    elif period == "凌晨" and hour == 12:
        hour = 0

    return hour, minute, rest


def parse_natural(text, today=None):
    """
    解析自然语言任务描述。
    返回 dict（title/due_date/due_time/priority/tags/context），无法解析出标题时返回 None。
    """
    if not isinstance(text, str) or not text.strip():
        return None

    today = today or date.today()
    working = text.strip()

    tags = []
    for match in TAG_RE.finditer(working):
        tag = match.group(1).strip(TAG_TRIM)
        if tag and tag not in tags:
            tags.append(tag)
    working = TAG_RE.sub(" ", working)

    context = None
    match = CONTEXT_RE.search(working)
    if match:
        context = match.group(1).strip(TAG_TRIM) or None
    working = CONTEXT_RE.sub(" ", working)

    priority, working = _parse_priority(working)
    due_date, working = _parse_date(working, today)
    hour, minute, working = _parse_time(working)

    title = re.sub(r"\s+", " ", working).strip(" ,，.。;；")
    if not title:
        return None

    return {
        "title": title[:200],
        "due_date": due_date.isoformat() if due_date else None,
        "due_time": f"{hour:02d}:{minute:02d}" if hour is not None else None,
        "priority": priority,
        "tags": tags[:5],
        "context": context[:20] if context else None,
    }
