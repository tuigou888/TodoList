# 每日待办事项管理系统

一个基于 Flask 的待办事项管理应用，支持用户注册登录、任务管理、定时邮件提醒、Docker 部署等功能。

![Python](https://img.shields.io/badge/Python-3.10-blue)
![Flask](https://img.shields.io/badge/Flask-3.1.0-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## 功能特性

- 用户注册与登录
- 找回密码功能
- 待办事项 CRUD 操作
- 今日/全部视图切换
- 定时邮件提醒（每日 7:00-23:00 每小时）
- 管理员后台管理
- Docker 支持
- 响应式设计
- 安全防护（SQL注入、XSS、CSP）

## 技术栈

- **后端**: Flask 3.1, Python 3.10
- **数据库**: SQLite
- **会话管理**: Flask-Session（服务器端存储）
- **前端**: HTML5, CSS3, JavaScript
- **部署**: Docker, Docker Compose, Gunicorn

## 快速开始

### Docker 部署（推荐）

```bash
# 克隆项目
git clone https://github.com/tuigou888/TodoList.git
cd TodoList

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置邮件等

# 启动应用
docker-compose up -d
```

访问 http://localhost:5000

### 本地运行

```bash
# 克隆项目
git clone https://github.com/tuigou888/TodoList.git
cd TodoList

# 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows
# 或
source venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env

# 运行应用
python app.py
```

访问 http://localhost:5000

## 环境变量配置

在 `.env` 文件中配置：

```env
# 密钥（必填）
SECRET_KEY=your-secret-key-here

# 邮件配置（可选）
MAIL_ENABLED=True
MAIL_SERVER=smtp.qq.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@qq.com
MAIL_PASSWORD=your-auth-code
MAIL_DEFAULT_SENDER=your-email@example.com

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
├── Dockerfile         # Docker 构建文件
├── docker-compose.yml # Docker Compose 配置
├── .env.example       # 环境变量示例
├── templates/         # HTML 模板
│   ├── index.html     # 主页面
│   ├── login.html    # 登录页
│   ├── register.html # 注册页
│   ├── admin.html    # 管理后台
│   ├── forgot_password.html
│   └── reset_password.html
├── README.md          # 项目文档
├── DEPLOYMENT.md      # 部署文档
├── SPEC.md           # 规格说明
└── MAIL_CONFIG.md    # 邮件配置指南
```

## 管理员功能

1. 访问 `/admin` 进入管理后台
2. 查看所有用户列表（支持搜索和分页）
3. 查看用户的待办事项
4. 添加/删除用户
5. 设置用户为管理员
6. 测试邮件发送功能

## API 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/login | 用户登录 |
| POST | /api/logout | 用户登出 |
| POST | /api/register | 用户注册 |
| POST | /api/forgot-password | 找回密码 |
| POST | /api/reset-password | 重置密码 |
| GET | /api/me | 获取当前用户信息 |
| GET | /api/todos | 获取待办事项列表 |
| POST | /api/todos | 创建待办事项 |
| PUT | /api/todos/<id> | 更新待办事项 |
| DELETE | /api/todos/<id> | 删除待办事项 |
| GET | /api/admin/users | 获取用户列表（管理员） |
| POST | /api/admin/users | 添加用户（管理员） |
| DELETE | /api/admin/users/<id> | 删除用户（管理员） |

## 安全特性

- SQL 注入防护（参数化查询）
- XSS 防护（HTML 转义）
- 内容安全策略 (CSP)
- 安全响应头（X-Frame-Options, X-Content-Type-Options）
- 跨域白名单管理
- Flask-Session 服务器端会话存储

## 部署文档

详细部署说明请参考 [DEPLOYMENT.md](./DEPLOYMENT.md)

## 许可证

MIT License
