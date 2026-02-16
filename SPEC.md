# 待办事项列表应用规格说明

## 1. 项目概述

- **项目名称**: Daily Todo List
- **项目类型**: Web应用 (Python Flask)
- **核心功能**: 每日待办事项管理，支持用户注册登录、管理员后台
- **目标用户**: 需要日常任务管理的人群

## 2. 技术栈

- **后端**: Python 3 + Flask
- **数据库**: SQLite (轻量级，无需额外配置)
- **前端**: HTML + CSS + JavaScript (原生，无框架依赖)
- **认证**: Session + 密码加密 (SHA-256)
- **部署**: 可通过 gunicorn 或直接运行 Flask

## 3. 功能列表

### 3.1 用户系统
- [x] 用户注册（用户名、密码、邮箱）
- [x] 用户登录/登出
- [x] 密码加密存储
- [x] Session会话管理
- [x] 记录最后登录时间
- [x] 邮箱验证（注册时必填）

### 3.2 待办事项管理
- [x] 查看当天所有待办事项
- [x] 新增待办事项（标题 + 可选描述）
- [x] 删除待办事项
- [x] 标记待办事项为已完成/未完成
- [x] 按日期筛选查看历史待办
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
- [x] 北京时间整点发送
- [x] 只向有待办事项的用户发送
- [x] 美观的HTML邮件模板
- [x] 支持多种邮箱服务（QQ、163、Gmail等）
- [x] 可配置提醒时间
- [x] 邮箱必填验证

### 3.5 数据持久化
- [x] 使用SQLite存储数据
- [x] 用户表：ID、用户名、密码、邮箱、管理员标识、创建时间、最后登录时间
- [x] 待办表：ID、标题、描述、完成状态、创建日期、用户ID

## 4. UI/UX 设计方向

### 4.1 整体风格
- 简洁现代的卡片式设计
- 响应式布局，适配桌面和移动端
- 渐变色背景提升视觉效果

### 4.2 色彩方案
- 主色调: 柔和的蓝色 (#4A90D9)
- 管理后台: 紫色渐变 (#667eea → #764ba2)
- 背景: 浅灰色 (#F5F7FA)
- 已完成事项: 绿色高亮 (#48BB78)
- 删除按钮: 红色警示 (#F56565)

### 4.3 布局
- **主页**: 日期显示 + 标题 + 用户信息 + 输入区域 + 待办列表
- **登录页**: 居中表单设计，渐变背景
- **注册页**: 用户名、邮箱、密码、确认密码
- **管理后台**: 用户列表表格 + 搜索 + 分页 + 操作按钮

## 5. API 设计

### 5.1 认证相关

| 方法 | 路由 | 功能 | 权限 |
|------|------|------|------|
| GET | /login | 登录页面 | 公开 |
| GET | /register | 注册页面 | 公开 |
| POST | /api/register | 用户注册 | 公开 |
| POST | /api/login | 用户登录 | 公开 |
| POST | /api/logout | 用户登出 | 需登录 |
| GET | /api/me | 获取当前用户信息 | 需登录 |

### 5.2 待办事项相关

| 方法 | 路由 | 功能 | 权限 |
|------|------|------|------|
| GET | / | 主页 | 需登录 |
| GET | /api/todos | 获取当天待办列表 | 需登录 |
| POST | /api/todos | 新增待办 | 需登录 |
| PUT | /api/todos/<id> | 更新待办状态 | 需登录 |
| DELETE | /api/todos/<id> | 删除待办 | 需登录 |
| GET | /api/todos?date=YYYY-MM-DD | 获取指定日期待办 | 需登录 |

### 5.3 管理后台相关

| 方法 | 路由 | 功能 | 权限 |
|------|------|------|------|
| GET | /admin | 管理后台页面 | 管理员 |
| GET | /api/admin/users | 获取用户列表（分页、搜索） | 管理员 |
| GET | /api/admin/users/<id> | 获取用户详情 | 管理员 |
| POST | /api/admin/users | 添加用户 | 管理员 |
| DELETE | /api/admin/users/<id> | 删除用户 | 管理员 |
| GET | /api/admin/users/<id>/todos | 获取用户待办事项 | 管理员 |

## 6. 数据库结构

### 6.1 用户表 (users)

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    email TEXT,
    is_admin INTEGER DEFAULT 0,
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
- Session 会话管理
- 所有 API 端点需要登录认证
- 管理后台需要管理员权限
- 用户数据完全隔离
- 防止管理员删除自己的账户

## 8. 部署说明

详细的部署文档请参考 [DEPLOYMENT.md](./DEPLOYMENT.md)

### 快速启动

```bash
# 安装依赖
pip install flask

# 运行数据库迁移（首次运行）
python migrate_db.py

# 启动应用
python app.py
```

访问 http://localhost:5000 即可使用

默认管理员账户：
- 用户名: admin
- 密码: admin123
