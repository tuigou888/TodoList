"""健康检查测试。"""


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "db": "ok"}


def test_healthz_is_public(tmp_path, monkeypatch):
    import app as app_module

    monkeypatch.setattr(app_module, "DB_NAME", str(tmp_path / "health.db"))
    app_module.init_db()
    with app_module.app.test_client() as client:
        assert client.get("/healthz").status_code == 200
