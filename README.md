# 每日待办事项管理系统

一个基于 Flask 的待办事项管理应用，支持用户注册登录、任务管理、定时邮件提醒等功能。

![Python](https://img.shields.io/badge/Python-3.10-blue)
![Flask](https://img.shields.io/badge/Flask-3.1.0-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## 功能特性

- 用户注册与登录
- 待办事项 CRUD 操作
- 今日/全部视图切换
- 定时邮件提醒（每日 7:00-23:00 每小时）
- 管理员后台管理
- 找回密码功能
- Docker 支持
- 响应式设计

## 技术栈

- **后端**: Flask 3.1, Python 3.10
- **数据库**: SQLite
- **前端**: HTML5, CSS3, JavaScript
- **部署**: Docker, Gunicorn

## 快速开始

### 本地运行

```bash
# 克隆项目
git clone https://github.com/tuigou888/TodoList.git
cd TodoList

# 创建虚拟环境（可选）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置邮件等

# 运行应用
python app.py
```

访问 http://localhost:5000

### Docker 部署

```bash
# 构建镜像
docker build -t todo-list-app .

# 运行容器
docker run -d -p 5000:5000 --env-file .env todo-list-app
```

### Docker Compose 部署（推荐）

```yaml
# docker-compose.yml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "5000:5000"
    env_file:
      - .env
    volumes:
      - ./todos.db:/app/todos.db
      - ./flask_session:/app/flask_session
    restart: unless-stopped
```

```bash
docker-compose up -d
```

## 环境变量配置

在 `.env` 文件中配置以下变量：

```env
# 密钥（必填）
SECRET_KEY=your-secret-key-here

# 邮件配置（可选，用于发送提醒邮件）
MAIL_SERVER=smtp.qq.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@qq.com
MAIL_PASSWORD=your-auth-code

# 跨域配置（可选）
CORS_ENABLED=True
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5000
```

## 项目结构

```
TodoList/
├── app.py              # 主应用文件
├── config.py           # 配置文件
├── requirements.txt    # Python 依赖
├── Dockerfile          # Docker 构建文件
├── .env.example        # 环境变量示例
├── templates/          # HTML 模板
│   ├── index.html      # 主页面
│   ├── login.html      # 登录页
│   ├── register.html   # 注册页
│   ├── admin.html      # 管理后台
│   ├── forgot_password.html
│   └── reset_password.html
└── ...
```

## 管理员功能

1. 访问 `/admin` 进入管理后台
2. 查看所有用户列表
3. 查看用户的待办事项
4. 添加/删除用户
5. 测试邮件发送功能

## API 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/login | 用户登录 |
| POST | /api/logout | 用户登出 |
| POST | /api/register | 用户注册 |
| GET | /api/me | 获取当前用户信息 |
| GET | /api/todos | 获取待办事项列表 |
| POST | /api/todos | 创建待办事项 |
| PUT | /api/todos/<id> | 更新待办事项 |
| DELETE | /api/todos/<id> | 删除待办事项 |
| GET | /api/admin/users | 获取用户列表（管理员） |

## 安全特性

- SQL 注入防护（参数化查询）
- XSS 防护（HTML 转义）
- CSRF 防护
- 内容安全策略 (CSP)
- 安全响应头

## 许可证

MIT License
