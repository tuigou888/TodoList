"""自然语言解析测试。"""

from datetime import date

from todo_app.nlp import parse_natural


def test_parse_full_sentence():
    parsed = parse_natural(
        "明天下午3点 交报告 !高 #工作 @电脑", today=date(2026, 10, 18)
    )
    assert parsed == {
        "title": "交报告",
        "due_date": "2026-10-19",
        "due_time": "15:00",
        "priority": 3,
        "tags": ["工作"],
        "context": "电脑",
    }


def test_parse_next_weekday_and_clock():
    parsed = parse_natural("下周一 10:30 开会", today=date(2026, 10, 18))
    assert parsed["due_date"] == "2026-10-19"
    assert parsed["due_time"] == "10:30"
    assert parsed["title"] == "开会"


def test_parse_month_day_and_tags():
    parsed = parse_natural("10月20日 买牛奶 #生活", today=date(2026, 10, 18))
    assert parsed["due_date"] == "2026-10-20"
    assert parsed["tags"] == ["生活"]
    assert parsed["title"] == "买牛奶"


def test_parse_explicit_year():
    parsed = parse_natural("2026-12-31 写总结")
    assert parsed["due_date"] == "2026-12-31"
    assert parsed["title"] == "写总结"


def test_parse_bang_priority():
    parsed = parse_natural("!!! 紧急修复")
    assert parsed["priority"] == 3
    assert parsed["title"] == "紧急修复"


def test_parse_evening_time_without_date():
    parsed = parse_natural("晚上8点 跑步", today=date(2026, 10, 18))
    assert parsed["due_date"] is None
    assert parsed["due_time"] == "20:00"
    assert parsed["title"] == "跑步"


def test_parse_multiple_tags_and_numeric_priority():
    parsed = parse_natural("明天 15:30 交周报 !2 #工作 #重要")
    assert parsed["priority"] == 2
    assert parsed["tags"] == ["工作", "重要"]
    assert parsed["due_time"] == "15:30"


def test_parse_returns_none_without_title():
    assert parse_natural("#标签") is None
    assert parse_natural("") is None
