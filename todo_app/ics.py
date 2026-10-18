"""生成 iCalendar (ICS) 订阅内容。"""

import json
from datetime import datetime, timezone

PRIORITY_MAP = {3: 1, 2: 5, 1: 9}


def _escape(value):
    text = "" if value is None else str(value)
    return (
        text.replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def build_ics(todos):
    """把有截止日期的未完成待办转换为 ICS 日历。"""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Todo List//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:每日待办",
        "X-WR-TIMEZONE:Asia/Shanghai",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
    ]

    for todo in todos:
        due_date = todo["due_date"]
        if not due_date:
            continue

        day = str(due_date).replace("-", "")
        if todo["due_time"]:
            start = (
                "DTSTART:"
                + day
                + "T"
                + str(todo["due_time"]).replace(":", "")
                + "00"
            )
        else:
            start = "DTSTART;VALUE=DATE:" + day

        details = []
        if todo["description"]:
            details.append(todo["description"])
        if todo["tags"]:
            try:
                tags = json.loads(todo["tags"])
            except (TypeError, ValueError):
                tags = []
            if isinstance(tags, list) and tags:
                details.append("标签: " + " ".join("#" + str(tag) for tag in tags))
        if todo["context"]:
            details.append("上下文: @" + todo["context"])
        description = "\n".join(details) or "待办事项"

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:todo-{todo['id']}@todo-list",
                f"DTSTAMP:{stamp}",
                start,
                f"SUMMARY:{_escape(todo['title'])}",
                f"DESCRIPTION:{_escape(description)}",
                "STATUS:CONFIRMED",
                f"PRIORITY:{PRIORITY_MAP.get(todo['priority'], 5)}",
                "BEGIN:VALARM",
                "TRIGGER:-PT30M",
                "ACTION:DISPLAY",
                "DESCRIPTION:待办提醒",
                "END:VALARM",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
