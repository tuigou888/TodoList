# 待办事项列表应用规格说明

## 1. 项目概述

- **项目名称**：Daily Todo List
- **项目类型**：Web 应用（Python Flask）
- **核心功能**：每日待办管理、截止日期/优先级、每日邮件提醒、个人设置、管理员后台
- **目标用户**：需要日常任务管理的人群

## 2. 技术栈

- **后端**：Python 3.10+、Flask 3.1
- **数据库**：SQLite（WAL、外键、查询索引）
- **前端**：HTML5 + CSS3 + 原生 JavaScript（无构建）
- **认证**：Flask-Session 服务器端会话 + `session_version` 失效机制
- **部署**：Docker、Docker Compose、Gunicorn
- **测试/检查**：pytest、ruff、GitHub Actions

## 3. 功能列表

### 3.1 用户系统

- [x] 注册（用户名、密码、邮箱）
- [x] 登录/登出
- [x] 密码哈希（Werkzeug scrypt，随机 salt）
- [x] 旧 SHA-256 哈希登录后自动升级
- [x] 会话管理（服务器端存储、会话版本失效）
- [x] 记录最后登录时间
- [x] 找回密码（数据库令牌、单次使用、限频）
- [x] 修改密码 / 修改邮箱
- [x] 退出所有设备

### 3.2 待办事项

- [x] 新增（标题、描述、截止日期、时间、优先级）
- [x] 编辑（标题、描述、截止日期、时间、优先级）
- [x] 删除
- [x] 完成/取消完成（记录完成时间）
- [x] 今天 / 所有视图
- [x] 状态 / 优先级 / 关键字筛选
- [x] 标签（#）与上下文（@）展示/筛选
- [x] 自然语言添加（本地规则解析）
- [x] 今日三件事（每天最多 3 项）
- [x] 按创建时间 / 截止日期 / 优先级排序
- [x] 统计（未完成、已完成、逾期、今日新增、MIT）
- [x] 用户数据隔离

### 3.3 个人设置

- [x] 基本信息展示（用户名、邮箱、角色）
- [x] 每日提醒开关与时间
- [x] 立即发送一次提醒（60 秒限频）
- [x] 每日/每周回顾开关与时间
- [x] 立即发送回顾
- [x] API 令牌生成/撤销
- [x] ICS 订阅链接生成/撤销
- [x] 修改密码（校验当前密码，成功后重新登录）
- [x] 修改邮箱（校验当前密码）
- [x] 退出所有设备

### 3.4 管理后台

- [x] 管理员认证
- [x] 概览统计（用户、7 天活跃、待办、未完成、逾期、完成率）
- [x] 用户列表（分页、搜索）
- [x] 用户详情与待办
- [x] 添加用户
- [x] 编辑用户（用户名、邮箱、管理员、启用状态）
- [x] 禁用/启用用户（旧会话立即失效）
- [x] 重置密码
- [x] 删除用户（级联删除待办与令牌）
- [x] 操作审计日志
- [x] 测试邮件

### 3.5 邮件提醒

- [x] 每个用户独立 `reminder_time`
- [x] 提醒开关
- [x] 每天最多一封（`last_reminded_on` 原子占位，多进程安全）
- [x] 只向有未完成待办的用户发送
- [x] HTML 模板、用户输入转义
- [x] 端口 465 SSL / 587 STARTTLS，超时保护
- [x] 邮件链接使用 `BASE_URL`
- [x] 设置页可立即发送一次
- [x] 每日回顾（完成/未完成/逾期/MIT）
- [x] 每周回顾（周一发送本周趋势）
- [x] 邮件 outbox 队列与失败重试

### 3.8 快速捕获

- [x] 本地自然语言解析（不依赖 AI/外部服务）
- [x] 中文日期/时间/优先级/标签/上下文
- [x] API 令牌（哈希存储、只显示一次、可撤销）
- [x] `/api/capture`（Bearer / 查询参数 / JSON）
- [x] `/capture` 书签页（令牌校验、Ctrl+Enter 提交）

### 3.9 日历订阅

- [x] `/calendar.ics?token=` 只读订阅
- [x] 仅导出未完成且有截止日期的待办
- [x] 定时事件、优先级、标签/上下文、提前 30 分钟提醒
- [x] 令牌可撤销，撤销后链接立即失效

### 3.7 体验与可访问性

- [x] PWA（manifest、service worker、可安装、应用壳离线）
- [x] 深色模式（跟随系统偏好 + 手动切换，localStorage 记忆）
- [x] 完成勾选支持键盘操作（role=checkbox / Enter / Space）
- [x] modal 使用 role=dialog / aria-modal，关闭后归还焦点
- [x] toast 使用 role=status / aria-live

### 3.6 安全与运维

- [x] 参数化 SQL
- [x] XSS 转义（页面 + 邮件）
- [x] CSP / X-Frame-Options / X-Content-Type-Options / Referrer-Policy
- [x] CORS 白名单（通配符不下发 credentials）
- [x] 请求体大小限制
- [x] SECRET_KEY 强校验（生产拒绝弱默认值）
- [x] 密码重置令牌限频与哈希存储
- [x] 管理员操作审计
- [x] `/healthz` 健康检查
- [x] Docker 非 root 运行

## 4. UI/UX 设计

### 4.1 整体风格

- 简洁现代的卡片式设计
- 响应式布局，适配桌面与移动端
- 和纸质感背景、暖色主色调
- 流畅的交互动画

### 4.2 色彩方案

- 主色：Terracotta `#C4664A`
- 背景：`#FAF8F5`
- 成功/完成：Sage `#7A9B76`
- 危险/逾期：`#D4503A`
- 文字：`#1A1A2E` / 灰阶

### 4.3 页面

- **主页**：视图切换、日期、统计、添加表单、筛选栏、待办列表、编辑弹窗
- **登录/注册/找回/重置**：居中卡片表单
- **设置页**：基本信息、提醒、修改密码、修改邮箱、退出所有设备
- **管理后台**：统计卡片、用户表格、编辑弹窗、操作日志

## 5. API 设计

### 5.1 认证与账号

| 方法 | 路由 | 功能 | 权限 |
| --- | --- | --- | --- |
| GET | `/login` `/register` `/forgot-password` | 页面 | 公开 |
| GET | `/reset-password/<token>` | 重置页（无效令牌 404） | 公开 |
| POST | `/api/register` | 注册 | 公开 |
| POST | `/api/login` | 登录 | 公开 |
| POST | `/api/logout` | 登出 | 公开 |
| POST | `/api/forgot-password` | 申请重置 | 公开 |
| POST | `/api/reset-password` | 重置密码 | 公开 |
| GET | `/api/me` | 当前用户 | 登录 |
| PUT | `/api/me/password` | 修改密码 | 登录 |
| PUT | `/api/me/email` | 修改邮箱 | 登录 |
| PUT | `/api/me/reminder` | 提醒设置 | 登录 |
| PUT | `/api/me/review` | 每日/每周回顾设置 | 登录 |
| POST | `/api/me/review/send` | 立即发送回顾 | 登录 |
| GET/POST/DELETE | `/api/me/api-token` | API 令牌状态/生成/撤销 | 登录 |
| GET/POST/DELETE | `/api/me/ics-token` | 订阅链接状态/生成/撤销 | 登录 |
| GET | `/capture` | 快速捕获页 | 令牌 |
| POST | `/api/me/logout-all` | 退出所有设备 | 登录 |
| GET | `/settings` | 设置页 | 登录 |

### 5.2 待办

| 方法 | 路由 | 功能 | 权限 |
| --- | --- | --- | --- |
| GET | `/api/todos` | 列表（`view`/`date`/`status`/`priority`/`tag`/`context`/`q`/`sort`/`limit`） | 登录 |
| POST | `/api/todos` | 新增（支持 `natural: true`、`due_time`/`tags`/`context`） | 登录 |
| PUT | `/api/todos/<id>` | 更新（title/description/due_date/due_time/priority/tags/context/completed） | 登录 |
| DELETE | `/api/todos/<id>` | 删除 | 登录 |
| GET | `/api/todos/mit` | 今日三件事 | 登录 |
| PUT | `/api/todos/<id>/mit` | 设置/取消今日三件事（每天最多 3 项） | 登录 |
| GET | `/api/todos/stats` | 统计（含 MIT） | 登录 |
| POST | `/api/capture` | 令牌快速捕获（Bearer/查询参数/JSON） | 令牌 |
| GET | `/calendar.ics` | ICS 只读订阅 | 令牌 |
| POST | `/api/send-reminder-now` | 立即提醒（60 秒限频） | 登录 |

### 5.3 管理

| 方法 | 路由 | 功能 | 权限 |
| --- | --- | --- | --- |
| GET | `/admin` | 后台页面 | 管理员 |
| GET | `/api/admin/users` | 用户列表（分页/搜索） | 管理员 |
| GET | `/api/admin/users/<id>` | 用户详情 | 管理员 |
| POST | `/api/admin/users` | 添加用户 | 管理员 |
| PUT | `/api/admin/users/<id>` | 编辑/禁用 | 管理员 |
| DELETE | `/api/admin/users/<id>` | 删除 | 管理员 |
| PUT | `/api/admin/users/<id>/password` | 重置密码 | 管理员 |
| GET | `/api/admin/users/<id>/todos` | 用户待办 | 管理员 |
| GET | `/api/admin/stats` | 概览 | 管理员 |
| GET | `/api/admin/audit-logs` | 审计日志 | 管理员 |
| POST | `/api/admin/test-email` | 测试邮件 | 管理员 |
| GET | `/healthz` | 健康检查 | 公开 |

## 6. 数据库结构

### 6.1 users

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    email TEXT,
    is_admin INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    reminder_time INTEGER DEFAULT 540,
    reminder_enabled INTEGER DEFAULT 1,
    last_reminded_on DATE,
    last_manual_reminder_at TIMESTAMP,
    session_version INTEGER DEFAULT 0,
    api_token_hash TEXT,
    api_token_created_at TIMESTAMP,
    review_enabled INTEGER DEFAULT 0,
    review_time INTEGER DEFAULT 1200,
    last_review_on DATE,
    last_weekly_review_on DATE,
    ics_token TEXT,
    created_at TIMESTAMP DEFAULT (DATETIME('now', 'localtime')),
    last_login_at TIMESTAMP
);
```

### 6.2 todos

```sql
CREATE TABLE todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    completed INTEGER DEFAULT 0,
    created_date DATE,
    created_at TIMESTAMP,
    due_date DATE,
    due_time TEXT,
    priority INTEGER DEFAULT 2,
    tags TEXT,
    context TEXT,
    is_mit INTEGER DEFAULT 0,
    mit_date DATE,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP,
    user_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

### 6.3 password_reset_tokens / password_reset_requests

```sql
CREATE TABLE password_reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash TEXT UNIQUE NOT NULL,
    user_id INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE password_reset_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    requested_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

### 6.4 audit_logs

```sql
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id INTEGER,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id INTEGER,
    detail TEXT,
    created_at TIMESTAMP NOT NULL
);
```

### 6.5 索引

`idx_todos_user_id`、`idx_todos_user_completed`、`idx_todos_user_date`、`idx_todos_user_due`、`idx_todos_user_priority`、`idx_users_email`、`idx_prt_user_id`、`idx_prt_expires`、`idx_prr_user_time`、`idx_audit_created`。

## 7. 安全特性

- Werkzeug scrypt 密码哈希（旧 SHA-256 自动升级）
- 密码重置令牌哈希存储、单次使用、1 小时过期、5 分钟最多 5 次
- `session_version` 会话失效
- SQL 参数化；动态字段名白名单
- 页面与邮件 HTML 转义
- CSP、X-Frame-Options、X-Content-Type-Options、Referrer-Policy、Permissions-Policy
- CORS 白名单，通配符不下发 credentials
- SECRET_KEY 强校验、请求体上限、统一 JSON 错误

## 8. 部署说明

### Docker（推荐）

```bash
cp .env.example .env
# 编辑 SECRET_KEY、BASE_URL、邮件配置
docker-compose up -d
```

健康检查：`http://localhost:5145/healthz`。容器以非 root 用户运行。

### 本地

```bash
pip install -r requirements.txt
python app.py
```

访问 http://localhost:5145 。

### 测试

```bash
pip install -r requirements-dev.txt
pytest -q
ruff check .
```

## 9. 项目结构

```
TodoList/
├── app.py
├── todo_app/
│   ├── db.py
│   ├── tokens.py
│   ├── outbox.py
│   ├── scheduler.py
│   ├── validators.py
│   ├── security.py
│   ├── mailer.py
│   └── audit.py
├── config.py
├── gunicorn.conf.py
├── migrate_db.py
├── docker-entrypoint.sh
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── tests/
├── templates/
├── .env.example
├── .github/workflows/ci.yml
├── README.md
├── DEPLOYMENT.md
├── DOCKER_DEPLOY.md
└── MAIL_CONFIG.md
```

## 10. 更新日志

- **v1.0**：初始版本
- **v2.0**：用户认证与管理后台
- **v3.0**：界面重构、Docker 支持
- **v3.1**：安全响应头、会话管理
- **v4.0**：截止日期/优先级/编辑/筛选、个人设置页、管理统计与审计；密码升级 scrypt；重置令牌落库；每日提醒按用户时间；pytest/ruff/CI；Docker 非 root 与健康检查
- **v4.1**：本地自然语言快速捕获与 API 令牌、`/capture` 书签页；今日三件事（MIT）；标签/上下文；每日/每周回顾邮件；ICS 只读日历订阅；PWA 图标与深色模式修复
