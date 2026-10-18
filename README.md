# 每日待办事项管理系统

一个基于 Flask + SQLite 的待办事项应用，支持截止日期/优先级、每日邮件提醒、个人设置与管理后台。

![Python](https://img.shields.io/badge/Python-3.10-blue)
![Flask](https://img.shields.io/badge/Flask-3.1.0-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## 功能特性

- 用户注册、登录、找回密码；密码使用 Werkzeug scrypt 哈希
- 待办事项：标题、描述、截止日期、优先级、完成状态、编辑、删除
- 今天 / 所有视图，按状态、优先级、关键字筛选，按创建时间 / 截止日期 / 优先级排序
- 统计：未完成、已完成、已逾期
- 每日提醒邮件：每个用户独立提醒时间与开关，每天最多一封；可在设置页立即发送一次
- 个人设置：修改密码、修改邮箱、退出所有设备
- 管理后台：统计卡片、用户搜索/分页/添加/编辑/禁用/删除/重置密码、操作审计、测试邮件
- 安全：参数化 SQL、HTML 转义、CSP/CORS 安全头、会话版本失效、请求体大小限制、旧密码哈希登录后自动升级
- 健康检查 `/healthz`；Docker 中通过 `gosu` 以非 root 用户运行
- pytest 测试套件与 ruff 检查，GitHub Actions CI

## 技术栈

- **后端**：Flask 3.1、Python 3.10+
- **数据库**：SQLite（WAL、外键、查询索引）
- **会话**：Flask-Session 文件存储 + `session_version` 失效机制
- **前端**：HTML5 + CSS3 + 原生 JavaScript（无构建步骤）
- **部署**：Docker、Docker Compose、Gunicorn
- **测试**：pytest；**代码检查**：ruff

## 快速开始

### Docker 部署（推荐）

```bash
git clone https://github.com/tuigou888/TodoList.git
cd TodoList

cp .env.example .env
# 编辑 .env：至少设置 SECRET_KEY、BASE_URL，以及邮件配置

docker-compose up -d
```

访问 http://localhost:5145 。健康检查：http://localhost:5145/healthz 。

### 本地运行

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux / macOS

pip install -r requirements.txt
cp .env.example .env
# 编辑 .env
python app.py
```

首次运行会自动创建数据库、补齐字段并创建索引；`python app.py` 会同时启动每日提醒调度器。

### 初始化管理员

```bash
# 不设置 ADMIN_PASSWORD 时会生成随机临时密码并打印到终端
python migrate_db.py
```

## 环境变量

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `SECRET_KEY` | Flask 密钥，至少 16 位随机字符串（生产必填） | 无（弱默认值会被拒绝） |
| `BASE_URL` | 站点对外地址，用于邮件中的链接 | `http://localhost:5145` |
| `DB_NAME` | SQLite 数据库路径 | `todos.db` |
| `SESSION_COOKIE_SECURE` | 仅 HTTPS 发送会话 Cookie | `False` |
| `SESSION_COOKIE_SAMESITE` | 会话 Cookie SameSite | `Lax` |
| `MAX_CONTENT_LENGTH` | 请求体上限（字节） | `2097152` |
| `MAIL_ENABLED` | 是否启用邮件 | `True` |
| `MAIL_SERVER` / `MAIL_PORT` | SMTP 地址与端口 | `smtp.qq.com` / `587` |
| `MAIL_USE_TLS` | 使用 STARTTLS（587） | `True` |
| `MAIL_USE_SSL` | 使用 SSL 直连（465） | `False` |
| `MAIL_TIMEOUT` | SMTP 超时（秒） | `15` |
| `MAIL_USERNAME` / `MAIL_PASSWORD` | SMTP 账号与授权码 | 空 |
| `MAIL_DEFAULT_SENDER` | 默认发件人 | `noreply@todoapp.com` |
| `CORS_ENABLED` | 是否启用跨域 | `True` |
| `ALLOWED_ORIGINS` | 允许的跨域来源，逗号分隔 | localhost 白名单 |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` / `ADMIN_EMAIL` | `migrate_db.py` 初始化管理员用 | `admin` / 随机 / `admin@example.com` |

> 465 端口（163、126 等）必须设置 `MAIL_USE_SSL=True`、`MAIL_USE_TLS=False`；587 端口使用 STARTTLS。详见 [MAIL_CONFIG.md](./MAIL_CONFIG.md)。

## 项目结构

```
TodoList/
├── app.py                  # 路由、认证、令牌流程、提醒调度、Flask 配置
├── todo_app/
│   ├── validators.py       # 输入校验、JSON 解析、待办序列化
│   ├── security.py         # 密码/令牌哈希
│   ├── mailer.py           # SMTP 发送与邮件模板
│   └── audit.py            # 审计日志
├── config.py               # 环境变量配置
├── gunicorn.conf.py        # 生产服务器配置与启动钩子
├── migrate_db.py           # 幂等迁移脚本
├── docker-entrypoint.sh    # 容器入口（修复 DB 挂载、降权启动）
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml          # pytest / ruff 配置
├── tests/                  # pytest 测试
├── templates/              # 7 个 HTML 模板
├── .env.example
├── DEPLOYMENT.md
├── DOCKER_DEPLOY.md
├── MAIL_CONFIG.md
├── SPEC.md
└── README.md
```

## 管理员功能

1. 访问 `/admin`（需管理员账户）
2. 查看用户总数、7 天活跃、待办总数、未完成、逾期、完成率
3. 搜索/分页用户；添加、编辑、禁用/启用、重置密码、删除用户
4. 查看用户待办详情
5. 查看最近操作审计日志
6. 发送测试邮件

## API 接口

| 方法 | 路径 | 描述 | 权限 |
| --- | --- | --- | --- |
| POST | `/api/register` | 注册 | 公开 |
| POST | `/api/login` | 登录 | 公开 |
| POST | `/api/logout` | 登出 | 公开 |
| POST | `/api/forgot-password` | 申请重置密码 | 公开 |
| POST | `/api/reset-password` | 使用令牌重置密码 | 公开 |
| GET | `/api/me` | 当前用户信息 | 登录 |
| PUT | `/api/me/password` | 修改密码 | 登录 |
| PUT | `/api/me/email` | 修改邮箱 | 登录 |
| PUT | `/api/me/reminder` | 修改提醒时间/开关 | 登录 |
| POST | `/api/me/logout-all` | 退出所有设备 | 登录 |
| GET | `/api/todos` | 列表（view/date/status/priority/q/sort/limit） | 登录 |
| POST | `/api/todos` | 新建（title/description/due_date/priority） | 登录 |
| PUT | `/api/todos/<id>` | 更新（含 completed） | 登录 |
| DELETE | `/api/todos/<id>` | 删除 | 登录 |
| GET | `/api/todos/stats` | 当前用户统计 | 登录 |
| POST | `/api/send-reminder-now` | 立即发送提醒（60 秒限频） | 登录 |
| GET | `/api/admin/users` | 用户列表（分页/搜索） | 管理员 |
| GET | `/api/admin/users/<id>` | 用户详情 | 管理员 |
| POST | `/api/admin/users` | 添加用户 | 管理员 |
| PUT | `/api/admin/users/<id>` | 编辑/禁用用户 | 管理员 |
| DELETE | `/api/admin/users/<id>` | 删除用户 | 管理员 |
| PUT | `/api/admin/users/<id>/password` | 重置密码 | 管理员 |
| GET | `/api/admin/users/<id>/todos` | 用户待办 | 管理员 |
| GET | `/api/admin/stats` | 管理概览 | 管理员 |
| GET | `/api/admin/audit-logs` | 最近操作日志 | 管理员 |
| GET | `/healthz` | 健康检查 | 公开 |

## 测试与代码检查

```bash
pip install -r requirements-dev.txt
pytest -q
ruff check .
```

CI 配置见 `.github/workflows/ci.yml`：Python 3.10/3.12 运行 ruff + pytest，并构建 Docker 镜像。

## 安全特性

- 密码使用 Werkzeug scrypt（随机 salt），历史 SHA-256 哈希登录后自动升级
- 密码重置令牌只以哈希形式落库，单次使用、1 小时过期、申请限频
- 会话版本机制：改密/重置/禁用/退出所有设备后旧会话立即失效
- 参数化 SQL；邮件与页面中的用户输入做 HTML 转义
- CSP、X-Frame-Options、X-Content-Type-Options、Referrer-Policy、Permissions-Policy
- 通配符 CORS 来源不会下发 credentials
- 请求体大小限制、统一 JSON 错误响应
- 管理员操作审计

## 部署文档

- [DEPLOYMENT.md](./DEPLOYMENT.md)
- [DOCKER_DEPLOY.md](./DOCKER_DEPLOY.md)
- [MAIL_CONFIG.md](./MAIL_CONFIG.md)

## 许可证

MIT License
