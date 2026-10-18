"""PWA、深色模式与无障碍接入测试。"""


def test_static_assets_are_served(client):
    assets = [
        ("/static/manifest.json", "application/json"),
        ("/static/theme.css", "text/css"),
        ("/static/theme.js", "javascript"),
        ("/static/sw.js", "javascript"),
        ("/static/icon.svg", "svg"),
    ]
    for path, content_type in assets:
        response = client.get(path)
        assert response.status_code == 200, path
        assert content_type in response.headers["Content-Type"], path


def test_login_page_has_theme_and_manifest(client):
    body = client.get("/login").get_data(as_text=True)
    assert 'rel="manifest"' in body
    assert "/static/theme.css" in body
    assert "/static/theme.js" in body
    assert 'role="status"' in body


def test_index_has_pwa_and_accessible_checkbox(auth_client):
    body = auth_client.get("/").get_data(as_text=True)
    assert "/static/theme.js" in body
    assert 'role="checkbox"' in body
    assert "handleCheckboxKey" in body
    assert "editModalTitle" in body
    assert 'aria-modal="true"' in body


def test_admin_modals_are_dialogs(admin_client):
    body = admin_client.get("/admin").get_data(as_text=True)
    assert 'role="dialog"' in body
    assert 'aria-modal="true"' in body
    assert "/static/theme.js" in body


def test_settings_page_has_theme(admin_client):
    body = admin_client.get("/settings").get_data(as_text=True)
    assert "/static/theme.css" in body
    assert "/static/theme.js" in body
