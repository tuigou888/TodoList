"""自然语言添加与快速捕获 API 测试。"""


def _token(client):
    response = client.post("/api/me/api-token")
    assert response.status_code == 200
    return response.get_json()["token"]


def test_natural_add_todo(auth_client):
    response = auth_client.post(
        "/api/todos",
        json={
            "title": "明天下午3点 交报告 !高 #工作 @电脑",
            "natural": True,
        },
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data["title"] == "交报告"
    assert data["due_time"] == "15:00"
    assert data["priority"] == 3
    assert data["tags"] == ["工作"]
    assert data["context"] == "电脑"


def test_natural_add_rejects_empty_title(auth_client):
    response = auth_client.post(
        "/api/todos", json={"title": "#只有标签", "natural": True}
    )
    assert response.status_code == 400


def test_capture_with_token(auth_client):
    token = _token(auth_client)

    response = auth_client.post(
        "/api/capture",
        json={"token": token, "text": "明天 15:30 交周报 !2 #工作"},
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data["title"] == "交周报"
    assert data["due_time"] == "15:30"
    assert data["priority"] == 2
    assert data["tags"] == ["工作"]


def test_capture_requires_valid_token(auth_client):
    assert auth_client.post("/api/capture", json={"text": "任务"}).status_code == 401
    assert (
        auth_client.post(
            "/api/capture", json={"token": "invalid", "text": "任务"}
        ).status_code
        == 401
    )


def test_capture_with_bearer_token(auth_client):
    token = _token(auth_client)
    response = auth_client.post(
        "/api/capture",
        json={"text": "买牛奶"},
        headers={"Authorization": "Bearer " + token},
    )
    assert response.status_code == 201


def test_capture_page_and_revoke(auth_client):
    token = _token(auth_client)
    assert auth_client.get(f"/capture?token={token}").status_code == 200
    assert auth_client.get("/capture?token=bad").status_code == 403

    assert auth_client.delete("/api/me/api-token").status_code == 200
    assert auth_client.get(f"/capture?token={token}").status_code == 403
    assert (
        auth_client.post(
            "/api/capture", json={"token": token, "text": "任务"}
        ).status_code
        == 401
    )


def test_tag_filter(auth_client):
    auth_client.post(
        "/api/todos", json={"title": "写方案 #工作", "natural": True}
    )
    auth_client.post(
        "/api/todos", json={"title": "买牛奶 #生活", "natural": True}
    )

    response = auth_client.get(
        "/api/todos", query_string={"view": "all", "tag": "工作"}
    )
    assert response.status_code == 200
    assert len(response.get_json()) == 1
    assert response.get_json()[0]["tags"] == ["工作"]
