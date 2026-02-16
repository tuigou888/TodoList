# 待办事项列表应用规格说明

## 1. 项目概述

- **项目名称**: Daily Todo List
- **项目类型**: Web应用 (Python Flask)
- **核心功能**: 每日待办事项管理，支持用户注册登录、管理员后台、Docker 部署
- **目标用户**: 需要日常任务管理的人群

## 2. 技术栈

- **后端**: Python 3.10 + Flask 3.1
- **数据库**: SQLite (轻量级，无需额外配置)
- **前端**: HTML5 + CSS3 + JavaScript (原生，无框架依赖)
- **认证**: Flask-Session (服务器端会话存储)
- **部署**: Docker, Docker Compose, Gunicorn

## 3. 功能列表

### 3.1 用户系统
- [x] 用户注册（用户名、密码、邮箱）
- [x] 用户登录/登出
- [x] 密码加密存储 (SHA-256)
- [x] Session 会话管理（服务器端存储）
- [x] 记录最后登录时间
- [x] 邮箱验证（注册时必填）
- [x] 找回密码功能

### 3.2 待办事项管理
- [x] 查看当天所有待办事项
- [x] 新增待办事项（标题 + 可选描述）
- [x] 删除待办事项
- [x] 标记待办事项为已完成/未完成
- [x] 按日期筛选查看历史待办
- [x] 今日/全部视图切换
- [x] 用户数据隔离（每个用户只能看到自己的待办）

### 3.3 管理后台
- [x] 管理员认证系统
- [x] 查看所有用户列表
- [x] 查看用户详细信息（注册时间、最后登录时间）
- [x] 查看用户的待办事项
- [x] 添加新用户（可设置管理员权限）
- [x] 删除用户
- [x] 搜索用户（按用户名或邮箱）
- [x] 分页显示用户列表

### 3.4 邮件通知
- [x] 定时邮件提醒（每小时检查）
- [x] 固定时间发送（7:00-23:00 每小时）
- [x] 只向有待办事项的用户发送
- [x] 美观的 HTML 邮件模板
- [x] 支持多种邮箱服务（QQ、163、Gmail等）
- [x] 邮箱必填验证

### 3.5 安全特性
- [x] SQL 注入防护（参数化查询）
- [x] XSS 防护（HTML 转义）
- [x] 内容安全策略 (CSP)
- [x] 安全响应头（X-Frame-Options, X-Content-Type-Options 等）
- [x] 跨域管理（CORS）

### 3.6 部署
- [x] Docker 支持
- [x] Docker Compose 支持
- [x] Gunicorn 生产服务器

## 4. UI/UX 设计

### 4.1 整体风格
- 简洁现代的卡片式设计
- 响应式布局，适配桌面和移动端
- 渐变色背景提升视觉效果
- 玻璃拟态（Glassmorphism）效果
- 流畅的交互动画

### 4.2 色彩方案
- 主色调: Indigo (#6366f1)
- 渐变背景: #667eea → #764ba2
- 背景: 浅灰色 (#F5F7FA)
- 成功: 绿色 (#10b981)
- 危险: 红色 (#ef4444)

### 4.3 布局
- **主页**: 日期显示 + 视图切换 + 用户信息 + 输入区域 + 待办列表
- **登录/注册**: 居中表单设计，渐变背景，动画效果
- **管理后台**: 用户列表表格 + 搜索 + 分页 + 操作按钮

## 5. API 设计

### 5.1 认证相关

| 方法 | 路由 | 功能 | 权限 |
|------|------|------|------|
| GET | /login | 登录页面 | 公开 |
| GET | /register | 注册页面 | 公开 |
| GET | /forgot-password | 找回密码页面 | 公开 |
| POST | /api/register | 用户注册 | 公开 |
| POST | /api/login | 用户登录 | 公开 |
| POST | /api/logout | 用户登出 | 需登录 |
| POST | /api/forgot-password | 找回密码 | 公开 |
| POST | /api/reset-password | 重置密码 | 公开 |
| GET | /api/me | 获取当前用户信息 | 需登录 |

### 5.2 待办事项相关

| 方法 | 路由 | 功能 | 权限 |
|------|------|------|------|
| GET | / | 主页 | 需登录 |
| GET | /api/todos | 获取当天待办列表 | 需登录 |
| GET | /api/todos?date=YYYY-MM-DD | 获取指定日期待办 | 需登录 |
| POST | /api/todos | 新增待办 | 需登录 |
| PUT | /api/todos/<id> | 更新待办状态 | 需登录 |
| DELETE | /api/todos/<id> | 删除待办 | 需登录 |

### 5.3 管理后台相关

| 方法 | 路由 | 功能 | 权限 |
|------|------|------|------|
| GET | /admin | 管理后台页面 | 管理员 |
| GET | /api/admin/users | 获取用户列表（分页、搜索） | 管理员 |
| GET | /api/admin/users/<id> | 获取用户详情 | 管理员 |
| POST | /api/admin/users | 添加用户 | 管理员 |
| DELETE | /api/admin/users/<id> | 删除用户 | 管理员 |
| GET | /api/admin/users/<id>/todos | 获取用户待办事项 | 管理员 |
| POST | /api/admin/test-email | 测试邮件发送 | 管理员 |

## 6. 数据库结构

### 6.1 用户表 (users)

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    email TEXT,
    is_admin INTEGER DEFAULT 0,
    reminder_time INTEGER DEFAULT 540,
    created_at TIMESTAMP DEFAULT (DATETIME('now', 'localtime')),
    last_login_at TIMESTAMP
);
```

### 6.2 待办事项表 (todos)

```sql
CREATE TABLE todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    completed INTEGER DEFAULT 0,
    created_date DATE DEFAULT (DATE('now', 'localtime')),
    created_at TIMESTAMP DEFAULT (DATETIME('now', 'localtime')),
    user_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

## 7. 安全特性

- 密码使用 SHA-256 加密存储
- Flask-Session 服务器端会话管理
- SQL 参数化查询
- HTML 内容转义
- Content-Security-Policy 响应头
- X-Frame-Options 防止点击劫持
- X-Content-Type-Options 防止 MIME 嗅探
- 跨域白名单管理

## 8. 部署说明

### Docker 部署（推荐）

```bash
# 克隆项目
git clone https://github.com/tuigou888/TodoList.git

# 配置环境变量
cp .env.example .env

# 启动
docker-compose up -d
```

### 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python app.py
```

访问 http://localhost:5000

## 9. 项目结构

```
TodoList/
├── app.py              # 主应用文件
├── config.py           # 配置文件
├── requirements.txt    # Python 依赖
├── Dockerfile          # Docker 构建文件
├── docker-compose.yml  # Docker Compose 配置
├── .env.example       # 环境变量示例
├── .gitignore         # Git 忽略文件
├── .dockerignore      # Docker 忽略文件
├── templates/          # HTML 模板
│   ├── index.html     # 主页面
│   ├── login.html     # 登录页
│   ├── register.html  # 注册页
│   ├── admin.html    # 管理后台
│   ├── forgot_password.html
│   └── reset_password.html
└── README.md          # 项目文档
```

## 10. 更新日志

- **v1.0**: 初始版本
- **v2.0**: 添加用户认证和管理后台
- **v3.0**: 美化界面，添加 Docker 支持
- **v3.1**: 添加安全特性，优化会话管理
