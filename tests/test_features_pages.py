"""新功能页面接入测试。"""


def test_index_has_mit_and_natural_language(auth_client):
    body = auth_client.get("/").get_data(as_text=True)
    assert "今日三件事" in body
    assert 'id="mitList"' in body
    assert "natural: true" in body
    assert "btn-mit" in body


def test_settings_has_new_cards(auth_client):
    body = auth_client.get("/settings").get_data(as_text=True)
    for text in ("每日回顾", "快速捕获", "日历订阅"):
        assert text in body
    assert 'id="reviewForm"' in body
    assert 'id="createTokenBtn"' in body
    assert 'id="createIcsBtn"' in body


def test_capture_page(auth_client):
    token = auth_client.post("/api/me/api-token").get_json()["token"]
    response = auth_client.get(f"/capture?token={token}")
    assert response.status_code == 200
    assert "快速捕获" in response.get_data(as_text=True)

    assert auth_client.get("/capture?token=bad").status_code == 403
