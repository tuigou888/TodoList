# Docker 部署教程

本教程详细介绍如何使用 Docker 部署每日待办事项应用。

## 目录

- [环境准备](#环境准备)
- [快速部署](#快速部署)
- [手动构建部署](#手动构建部署)
- [配置说明](#配置说明)
- [常见问题](#常见问题)

---

## 环境准备

### 1. 安装 Docker

**Windows:**

- 下载 [Docker Desktop](https://www.docker.com/products/docker-desktop)
- 安装并启动 Docker Desktop
- 确保 WSL2 已启用（Windows 11/10）

**Linux (Ubuntu):**

```bash
sudo apt update
sudo apt install docker.io docker-compose
sudo systemctl start docker
sudo systemctl enable docker
```

**macOS:**

- 下载 [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop)
- 安装并启动

### 2. 验证安装

```bash
docker --version
docker-compose --version
```

---

## 快速部署

### 步骤 1: 克隆项目

```bash
git clone https://github.com/tuigou888/TodoList.git
cd TodoList
```

### 步骤 2: 配置环境变量

```bash
# 复制配置文件
copy .env.example .env    # Windows
# 或
cp .env.example .env     # Linux/Mac
```

编辑 `.env` 文件，配置以下内容：

```env
# 密钥（必须修改）
SECRET_KEY=your-random-secret-key

# 邮件配置（可选）
MAIL_ENABLED=True
MAIL_SERVER=smtp.qq.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@qq.com
MAIL_PASSWORD=your-auth-code
MAIL_DEFAULT_SENDER=your-email@qq.com
```

**如何生成 SECRET_KEY:**

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 步骤 3: 启动应用

```bash
# 构建并启动（首次运行）
docker-compose up -d

# 查看运行状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 步骤 4: 访问应用

打开浏览器访问：**http://localhost:5145**

---

## 手动构建部署

如果不使用 docker-compose，可以手动构建：

### 步骤 1: 构建镜像

```bash
docker build -t todo-list-app .
```

### 步骤 2: 运行容器

```bash
docker run -d \
  --name todo-list \
  -p 5145:5145 \
  --env-file .env \
  -v ./todos.db:/app/todos.db \
  todo-list-app
```

### 步骤 3: 管理容器

```bash
# 查看运行状态
docker ps

# 查看日志
docker logs -f todo-list

# 停止容器
docker stop todo-list

# 启动容器
docker start todo-list

# 删除容器
docker rm todo-list
```

---

## Docker Compose 常用命令

| 命令                       | 说明           |
| -------------------------- | -------------- |
| `docker-compose up -d`   | 后台启动       |
| `docker-compose down`    | 停止并删除容器 |
| `docker-compose restart` | 重启           |
| `docker-compose logs -f` | 查看日志       |
| `docker-compose ps`      | 查看状态       |
| `docker-compose build`   | 重新构建       |

---

## 配置说明

### 端口映射

docker-compose.yml 中配置：

```yaml
ports:
  - "5145:5145"
```

- **左边 5145**：宿主机端口（访问的端口）
- **右边 5145**：容器内端口

如需修改，编辑 `docker-compose.yml`。

### 数据持久化

应用数据存储在：

- `todos.db` - SQLite 数据库
- `flask_session/` - Session 文件

这些数据在容器重启后会保留。

### 健康检查

Docker Compose 配置了健康检查：

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:5145/"]
```

---

## 常见问题

### Q1: 端口被占用

```bash
# 查找占用端口的进程
netstat -tlnp | grep :5145   # Linux
netstat -ano | findstr :5145  # Windows

# 修改端口
# 编辑 docker-compose.yml，将 5145:5145 改为其他端口
```

### Q2: 数据库权限问题

```bash
# Linux 下修改权限
sudo chown -R 1000:1000 .
```

### Q3: 容器内无法访问数据库

```bash
# 检查数据库文件是否存在
ls -la todos.db

# 如果不存在，手动创建
touch todos.db
```

### Q4: 邮件发送失败

1. 检查 `.env` 配置是否正确
2. 确认邮箱 SMTP 服务已开启
3. 使用授权码而非登录密码

### Q5: 查看容器日志

```bash
# 所有日志
docker-compose logs

# 实时日志
docker-compose logs -f

# 最近 100 行
docker-compose logs --tail=100
```

### Q6: 更新应用

```bash
# 拉取最新代码
git pull origin main

# 重新构建并启动
docker-compose up -d --build

# 查看日志确认更新
docker-compose logs -f
```

---

## 生产环境建议

### 1. 使用域名

配置 Nginx 反向代理：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5145;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 2. HTTPS 配置

使用 Let's Encrypt 免费 SSL 证书：

```bash
# 安装 certbot
sudo apt install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d your-domain.com
```

### 3. 备份

```bash
# 备份数据库
cp todos.db todos.db.backup.$(date +%Y%m%d)

# 备份配置
cp .env .env.backup
```

### 4. 监控

使用 [Portainer](https://www.portainer.io/) 管理 Docker：

```bash
docker volume create portainer_data
docker run -d -p 9000:9000 -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data portainer/portainer
```

---

## 相关链接

- 项目地址: https://github.com/tuigou888/TodoList
- Flask 文档: https://flask.palletsprojects.com/
- Docker 文档: https://docs.docker.com/
