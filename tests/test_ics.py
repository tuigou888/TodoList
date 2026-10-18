"""ICS 日历订阅测试。"""


def _enable_ics(client):
    response = client.post("/api/me/ics-token")
    assert response.status_code == 200
    return response.get_json()["url"].split("token=")[-1]


def test_ics_feed(auth_client):
    auth_client.post(
        "/api/todos",
        json={
            "title": "写报告",
            "due_date": "2026-12-31",
            "due_time": "15:00",
            "priority": 3,
            "tags": ["工作"],
        },
    )
    auth_client.post("/api/todos", json={"title": "没有日期"})

    token = _enable_ics(auth_client)
    response = auth_client.get(f"/calendar.ics?token={token}")
    assert response.status_code == 200
    assert "text/calendar" in response.headers["Content-Type"]

    body = response.get_data(as_text=True)
    assert "BEGIN:VCALENDAR" in body
    assert "SUMMARY:写报告" in body
    assert "没有日期" not in body
    assert "DTSTART:20261231T150000" in body
    assert "PRIORITY:1" in body
    assert "TRIGGER:-PT30M" in body


def test_ics_invalid_and_revoke(auth_client):
    assert auth_client.get("/calendar.ics?token=bad").status_code == 403

    token = _enable_ics(auth_client)
    assert auth_client.get(f"/calendar.ics?token={token}").status_code == 200
    assert auth_client.delete("/api/me/ics-token").status_code == 200
    assert auth_client.get(f"/calendar.ics?token={token}").status_code == 403


def test_ics_escapes_and_omits_completed(auth_client):
    completed_id = auth_client.post(
        "/api/todos",
        json={"title": "买牛奶,面包;回家", "due_date": "2026-12-31"},
    ).get_json()["id"]
    auth_client.put(f"/api/todos/{completed_id}", json={"completed": True})
    auth_client.post(
        "/api/todos", json={"title": "未完成,任务", "due_date": "2026-12-30"}
    )

    token = _enable_ics(auth_client)
    body = auth_client.get(f"/calendar.ics?token={token}").get_data(as_text=True)

    assert "买牛奶" not in body
    assert "未完成\\,任务" in body
