# AGENTS.md

## 交互要求

- Thinking 思考过程用中文表述
- Reply 回答也要用中文回复

## Commands

| Action       | Command                                                                                          |
| ------------ | ------------------------------------------------------------------------------------------------ |
| Dev server   | `python app.py`（端口 5145，debug，自动启动提醒调度器）                                          |
| Production   | `gunicorn -c gunicorn.conf.py app:app`（4 workers）                                              |
| Docker       | `docker-compose up -d`                                                                           |
| DB migration | `python migrate_db.py`（补字段/表/索引；仅在没有任何管理员时创建管理员）                         |
| Install deps | `pip install -r requirements.txt`                                                                |
| Dev deps     | `pip install -r requirements-dev.txt`（pytest + ruff）                                           |
| Test         | `pytest -q`                                                                                      |
| Lint         | `ruff check .`                                                                                   |

## Setup

1. `cp .env.example .env` → 设置 `SECRET_KEY`（必填，至少 16 位随机字符串）与 `BASE_URL`
2. `python -m venv venv` + 激活
3. `pip install -r requirements.txt`
4. `python app.py` → 首次运行自动建库并补字段

## Architecture

- **Entry**：`app.py` —— Flask 配置、认证装饰器、密码重置路由、待办/管理/设置路由。
- **Shared modules**：`todo_app/`
  - `db.py`：数据库连接、`init_db`、字段迁移、时间工具
  - `validators.py`：输入校验、JSON 请求解析、待办序列化
  - `security.py`：密码哈希（Werkzeug scrypt）、旧 SHA-256 校验与升级、令牌哈希
  - `tokens.py`：密码重置令牌生成、校验、消耗与限频
  - `mailer.py`：SMTP 发送（SSL/STARTTLS、超时）与提醒邮件模板
  - `outbox.py`：邮件 outbox 队列、退避重试与清理
  - `scheduler.py`：每日提醒、手动提醒与邮件队列调度
  - `audit.py`：管理员操作审计日志
- **DB**：SQLite，路径由 `DB_NAME` 环境变量决定（默认 `todos.db`）。WAL、外键开启、查询索引齐全；`init_db()` 幂等补字段。
- **Templates**：`templates/` 共 7 个 HTML（index/login/register/admin/settings/forgot/reset）。内联 CSS/JS，无构建步骤。
- **Session**：Flask-Session 文件存储；`users.session_version` 用于在改密、重置密码、禁用、退出所有设备后使旧会话立即失效。
- **Reminder**：后台 daemon 线程，每分钟检查；按用户 `reminder_time` 每天最多一封，`last_reminded_on` 在数据库层原子占位，多 worker 安全。
- **PWA/Theme**：`static/manifest.json`、`static/sw.js`、`static/theme.css`、`static/theme.js`；深色模式通过 `html.dark` 覆盖 CSS 变量，所有页面在 `</head>`/`</body>` 接入。
- **Timezone**：Docker 设置 `TZ=Asia/Shanghai`；Windows 本地遵循系统时区（`os.environ["TZ"]` 在 Windows 不生效）。

## Key Quirks

- **密码**：Werkzeug `scrypt` 哈希；历史 SHA-256 哈希在登录成功后自动升级。
- **重置令牌**：存于数据库 `password_reset_tokens`（只存哈希、1 小时有效、单次使用、每用户最多 3 个）；请求流水在 `password_reset_requests`，5 分钟内最多 5 次。
- **邮件**：465 端口需 `MAIL_USE_SSL=True`，587 端口用 `MAIL_USE_TLS=True`；`MAIL_TIMEOUT` 默认 15 秒；未配置账号密码时不会发送。
- **审计**：管理员创建/编辑/禁用/删除用户、重置密码，以及用户改密/改邮箱/退出所有设备，写入 `audit_logs`。
- **健康检查**：`GET /healthz` 返回数据库连通状态，供 Docker/反向代理探活。
- **Gunicorn**：`when_ready()` 先 `validate_config(strict=True)`，再 `init_db()`、`start_reminder_scheduler()`；配置错误会拒绝启动。
- **CORS/CSP**：统一在 `cors_response()` 中处理；通配符 Origin 不会同时下发 credentials。
- **`migrate_db.py`**：幂等迁移脚本，补字段/表/索引；不设置 `ADMIN_PASSWORD` 时生成随机临时密码并打印。

## File Boundaries

| Path                    | Role                                                       |
| ----------------------- | ---------------------------------------------------------- |
| `app.py`                | Flask 配置、认证、路由、登录限流                           |
| `todo_app/db.py`        | 数据库连接、建表/迁移、时间工具                            |
| `todo_app/tokens.py`    | 密码重置令牌                                               |
| `todo_app/outbox.py`    | 邮件队列与重试                                             |
| `todo_app/scheduler.py` | 每日提醒与邮件队列调度                                     |
| `todo_app/validators.py`| 输入校验与待办序列化                                       |
| `todo_app/security.py`  | 密码/令牌哈希                                              |
| `todo_app/mailer.py`    | 邮件发送与邮件模板                                         |
| `todo_app/audit.py`     | 审计日志                                                   |
| `config.py`             | `Config` 类，读取环境变量                                  |
| `gunicorn.conf.py`      | 生产服务器配置 + 启动钩子                                  |
| `migrate_db.py`         | 独立迁移脚本（手工运行）                                   |
| `templates/`            | 7 个页面模板                                               |
| `static/`               | PWA manifest、service worker、图标、主题 CSS/JS            |
| `tests/`                | pytest 测试套件                                            |
| `pyproject.toml`        | pytest / ruff 配置                                         |
| `requirements-dev.txt`  | 测试与 lint 依赖                                           |
| `docker-entrypoint.sh`  | 修复首次 bind mount 的 DB 目录问题，切换非 root 用户启动   |
| `todos.db`              | SQLite 数据库（gitignored，Docker 中挂载）                 |
| `flask_session/`        | 会话文件（gitignored，Docker 命名卷）                      |

## Docker Notes

- 端口 `5145`；健康检查 `GET /healthz`
- `todos.db` 从宿主机挂载：`./todos.db:/app/todos.db`；entrypoint 会处理"文件不存在被 Docker 建成目录"的首次启动问题
- `flask_session` 使用命名卷 `flask_session_data`
- 容器通过 `gosu` 以非 root 用户 `app` 运行
- 镜像内保留 `migrate_db.py`；`tests/`、`venv/` 被 `.dockerignore` 排除

## Conventions

- 测试使用 pytest，提交前运行 `pytest -q`；lint 使用 `ruff check .`。
- 所有 API 返回 JSON；页面返回 `render_template()`。
- 认证通过 `@login_required` / `@admin_required`，并校验 `session_version` 与账户启用状态。
- SQL 使用参数化查询（`?` 占位符）；动态字段名仅来自代码内白名单。
- 错误响应统一为 `jsonify({"error": "message"}), <status_code>`。
- `python app.py` 的 debug reloader 只会在工作子进程启动提醒调度器，避免重复发送。
