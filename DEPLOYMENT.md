# 部署文档

本文档提供 Daily Todo List 应用的详细部署指南。

## 目录

- [环境要求](#环境要求)
- [Docker 部署（推荐）](#docker-部署推荐)
- [本地运行](#本地运行)
- [配置说明](#配置说明)
- [常见问题](#常见问题)

## 环境要求

### 最低要求

- Python 3.8+
- SQLite 3
- 至少 100MB 可用磁盘空间
- 至少 256MB RAM

### 推荐配置

- Python 3.10
- 1GB+ RAM
- SSD 存储

## Docker 部署（推荐）

### 1. 克隆项目

```bash
git clone https://github.com/tuigou888/TodoList.git
cd TodoList
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，配置邮件等设置
```

### 3. 使用 Docker Compose 启动

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

### 4. 访问应用

访问 http://localhost:5000

### 5. 手动 Docker 构建

```bash
# 构建镜像
docker build -t todo-list-app .

# 运行容器
docker run -d -p 5000:5000 --env-file .env todo-list-app
```

### 6. Docker Compose 配置说明

```yaml
version: '3.8'

services:
  todo-app:
    build: .
    container_name: todo-list-app
    ports:
      - "5000:5000"
    env_file:
      - .env
    volumes:
      - ./todos.db:/app/todos.db
      - flask_session_data:/app/flask_session
    restart: unless-stopped
```

## 本地运行

### 1. 克隆项目

```bash
git clone https://github.com/tuigou888/TodoList.git
cd TodoList
```

### 2. 创建虚拟环境（推荐）

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件
```

### 5. 初始化数据库

首次运行会自动创建数据库。

### 6. 运行应用

```bash
# 开发模式
python app.py

# 或使用 Gunicorn（生产环境）
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

访问 http://localhost:5000

## 配置说明

### 环境变量

在 `.env` 文件中配置：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| SECRET_KEY | Flask 密钥（必填） | - |
| MAIL_ENABLED | 启用邮件服务 | True |
| MAIL_SERVER | SMTP 服务器 | smtp.qq.com |
| MAIL_PORT | SMTP 端口 | 587 |
| MAIL_USE_TLS | 使用 TLS | True |
| MAIL_USERNAME | 邮箱账号 | - |
| MAIL_PASSWORD | 邮箱密码/授权码 | - |
| MAIL_DEFAULT_SENDER | 发件人邮箱 | - |
| CORS_ENABLED | 启用跨域 | True |
| ALLOWED_ORIGINS | 允许的域名 | localhost:3000,5000 |

### 设置管理员

数据库创建后，可通过以下方式设置管理员：

```bash
sqlite3 todos.db
sqlite> UPDATE users SET is_admin = 1 WHERE username = 'your_username';
```

## 常见问题

### 1. 端口被占用

```bash
# 查找占用端口的进程
netstat -tlnp | grep :5000

# 或使用其他端口
docker-compose.yml 中修改 ports
```

### 2. 数据库权限问题

```bash
# 修改数据库文件权限
chmod 644 todos.db
```

### 3. Session 问题

- 使用 Docker 时，会话数据存储在卷中
- 重启容器后会话会丢失（正常行为）

### 4. 邮件发送失败

1. 检查 `.env` 配置
2. 确认邮箱 SMTP 服务已开启
3. 使用授权码而非登录密码

## 备份与恢复

### 备份数据库

```bash
# Docker 部署
docker cp todo-list-app:/app/todos.db ./todos.db.backup

# 本地
cp todos.db todos.db.backup.$(date +%Y%m%d)
```

### 恢复数据库

```bash
# Docker 部署
docker cp ./todos.db todo-list-app:/app/todos.db

# 本地
cp todos.db.backup todos.db
```

## 更新日志

- **v1.0**: 初始版本
- **v2.0**: 添加 Docker 支持
- **v2.1**: 美化界面，添加安全特性
