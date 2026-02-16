# 部署文档

本文档提供 Daily Todo List 应用的详细部署指南，包括命令行部署和宝塔面板部署两种方式。

## 目录

- [环境要求](#环境要求)
- [命令行部署](#命令行部署)
- [宝塔面板部署](#宝塔面板部署)
- [配置说明](#配置说明)
- [常见问题](#常见问题)

## 环境要求

### 最低要求

- Python 3.7+
- SQLite 3
- 至少 100MB 可用磁盘空间
- 至少 256MB RAM

### 推荐配置

- Python 3.9+
- 1GB+ RAM
- SSD 存储

## 命令行部署

### 1. 安装 Python 环境

#### Windows

```bash
# 下载并安装 Python 3.9+
# 访问 https://www.python.org/downloads/
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv -y
```

#### Linux (CentOS/RHEL)

```bash
sudo yum install python3 python3-pip -y
```

#### macOS

```bash
# 使用 Homebrew 安装
brew install python3
```

### 2. 克隆或下载项目

```bash
# 如果使用 Git
git clone <repository-url>
cd Todo-List

# 或者直接下载并解压项目文件
```

### 3. 创建虚拟环境（推荐）

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

### 4. 安装依赖

```bash
# 安装 Flask
pip install flask

# 生产环境推荐安装 gunicorn
pip install gunicorn
```

### 5. 配置应用

编辑 `app.py` 文件，修改以下配置：

```python
# 修改密钥（生产环境必须修改）
app.secret_key = 'your-secure-secret-key-change-this'

# 修改监听地址和端口（生产环境）
app.run(debug=False, host='0.0.0.0', port=5000)
```

### 6. 初始化数据库

```bash
# 运行数据库迁移脚本
python migrate_db.py
```

这将创建：
- `users` 表（用户数据）
- `todos` 表（待办事项）
- 默认管理员账户（用户名: admin, 密码: admin123）

**重要**: 首次部署后请立即修改默认管理员密码！

### 7. 配置邮件服务（可选）

详细的邮件配置指南请参考 [MAIL_CONFIG.md](./MAIL_CONFIG.md)

快速配置：

```bash
# 复制配置文件
cp .env.example .env

# 编辑配置文件，填写邮箱信息
# MAIL_ENABLED=True
# MAIL_SERVER=smtp.qq.com
# MAIL_USERNAME=your-email@qq.com
# MAIL_PASSWORD=your-password
```

### 8. 开发模式运行

```bash
python app.py
```

访问 http://localhost:5000

### 9. 生产环境部署

#### 使用 Gunicorn（推荐）

```bash
# 安装 Gunicorn
pip install gunicorn

# 启动应用（4个工作进程）
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# 后台运行
nohup gunicorn -w 4 -b 0.0.0.0:5000 app:app > app.log 2>&1 &

# 指定日志文件
gunicorn -w 4 -b 0.0.0.0:5000 --access-logfile access.log --error-logfile error.log app:app
```

#### 使用 Systemd（Linux 服务）

创建服务文件 `/etc/systemd/system/todo-app.service`:

```ini
[Unit]
Description=Todo List Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/Todo-List
Environment="PATH=/path/to/Todo-List/venv/bin"
ExecStart=/path/to/Todo-List/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable todo-app
sudo systemctl start todo-app
sudo systemctl status todo-app
```

#### 使用 Supervisor（进程管理）

安装 Supervisor：

```bash
sudo apt install supervisor -y  # Ubuntu/Debian
sudo yum install supervisor -y  # CentOS/RHEL
```

创建配置文件 `/etc/supervisor/conf.d/todo-app.conf`:

```ini
[program:todo-app]
directory=/path/to/Todo-List
command=/path/to/Todo-List/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/todo-app.err.log
stdout_logfile=/var/log/todo-app.out.log
```

启动服务：

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start todo-app
```

### 9. 配置 Nginx 反向代理（推荐）

安装 Nginx：

```bash
sudo apt install nginx -y  # Ubuntu/Debian
sudo yum install nginx -y  # CentOS/RHEL
```

创建配置文件 `/etc/nginx/sites-available/todo-app`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/todo-app /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 10. 配置 HTTPS（使用 Let's Encrypt）

```bash
# 安装 Certbot
sudo apt install certbot python3-certbot-nginx -y

# 获取证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo certbot renew --dry-run
```

## 宝塔面板部署

### 1. 安装宝塔面板

#### Linux

```bash
# CentOS
yum install -y wget && wget -O install.sh http://download.bt.cn/install/install_6.0.sh && sh install.sh

# Ubuntu/Debian
wget -O install.sh http://download.bt.cn/install/install-ubuntu_6.0.sh && sudo bash install.sh
```

安装完成后，访问 `http://服务器IP:8888`，使用宝塔面板提供的账号密码登录。

### 2. 安装 Python 环境

在宝塔面板中：

1. 进入 **软件商店**
2. 搜索并安装 **Python项目管理器**（或直接安装 Python）
3. 安装 Python 3.9 或更高版本

### 3. 上传项目文件

**方式一：使用宝塔文件管理器**

1. 进入 **文件** 标签
2. 进入 `/www/wwwroot/` 目录
3. 创建新文件夹 `todo-app`
4. 将项目文件上传到该目录

**方式二：使用 Git**

1. 在宝塔终端中执行：

```bash
cd /www/wwwroot/
git clone <repository-url> todo-app
cd todo-app
```

### 4. 安装项目依赖

在宝塔终端中：

```bash
cd /www/wwwroot/todo-app

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install flask gunicorn
```

### 5. 初始化数据库

```bash
# 在项目目录下执行
python migrate_db.py
```

### 6. 修改配置

编辑 `app.py`：

```python
# 修改密钥
app.secret_key = 'your-secure-secret-key-here'

# 关闭调试模式（生产环境）
app.run(debug=False, host='0.0.0.0', port=5000)
```

### 7. 创建 Python 项目

1. 在宝塔面板进入 **软件商店** → **Python项目管理器**
2. 点击 **添加项目**
3. 填写项目信息：
   - **项目名称**: todo-app
   - **项目路径**: `/www/wwwroot/todo-app`
   - **Python版本**: 选择 3.9+
   - **启动文件**: `app.py`
   - **端口**: 5000（或自定义）
   - **框架**: Flask
4. 点击 **提交**

### 8. 配置网站

1. 在宝塔面板进入 **网站** 标签
2. 点击 **添加站点**
3. 填写站点信息：
   - **域名**: 填写你的域名
   - **根目录**: `/www/wwwroot/todo-app`
   - **PHP版本**: 纯静态
4. 点击 **提交**

### 9. 配置反向代理

1. 进入刚创建的站点设置
2. 点击 **反向代理**
3. 添加反向代理：
   - **代理名称**: todo-app
   - **目标URL**: `http://127.0.0.1:5000`
   - **发送域名**: `$host`
4. 点击 **提交**

### 10. 配置 SSL 证书（可选但推荐）

1. 进入站点设置
2. 点击 **SSL**
3. 选择 **Let's Encrypt**
4. 填写邮箱地址
5. 点击 **申请**
6. 开启 **强制HTTPS**

### 11. 启动项目

在 **Python项目管理器** 中：

1. 找到 `todo-app` 项目
2. 点击 **启动**

### 12. 查看日志

在 **Python项目管理器** 中：

1. 点击项目名称
2. 查看 **日志** 标签
3. 可以查看应用运行日志

## 配置说明

### 修改管理员密码

首次部署后，建议立即修改默认管理员密码：

**方式一：通过管理后台**

1. 使用管理员账户登录
2. 进入管理后台
3. 删除旧管理员账户
4. 创建新的管理员账户

**方式二：直接修改数据库**

```bash
# 进入 SQLite
sqlite3 todos.db

# 更新密码（密码需要加密）
UPDATE users SET password = 'new-hashed-password' WHERE username = 'admin';

# 退出
.quit
```

### 修改端口

编辑 `app.py`:

```python
app.run(host='0.0.0.0', port=8080)  # 修改为 8080
```

或使用 Gunicorn:

```bash
gunicorn -w 4 -b 0.0.0.0:8080 app:app
```

### 修改数据库位置

编辑 `app.py`:

```python
DB_NAME = "/path/to/your/database.db"
```

### 修改 Session 密钥

编辑 `app.py`:

```python
app.secret_key = 'your-very-long-and-random-secret-key'
```

生成随机密钥：

```python
import secrets
print(secrets.token_hex(32))
```

## 常见问题

### 1. 端口被占用

**问题**: 启动时提示端口已被使用

**解决方案**:

```bash
# 查找占用端口的进程
netstat -tlnp | grep :5000  # Linux
netstat -ano | findstr :5000   # Windows

# 杀死进程
kill -9 <PID>  # Linux
taskkill /PID <PID> /F  # Windows

# 或使用其他端口
python app.py  # 修改 app.py 中的端口
```

### 2. 权限错误

**问题**: 无法写入数据库或日志文件

**解决方案**:

```bash
# 修改文件权限
chmod 755 /path/to/Todo-List
chmod 644 /path/to/Todo-List/todos.db

# 或修改所有者
chown www-data:www-data /path/to/Todo-List
```

### 3. 数据库锁定

**问题**: SQLite 数据库被锁定

**解决方案**:

```bash
# 删除锁文件
rm -f todos.db-wal todos.db-shm

# 或重启应用
```

### 4. 依赖安装失败

**问题**: pip install 失败

**解决方案**:

```bash
# 使用国内镜像
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple flask

# 升级 pip
pip install --upgrade pip

# 使用虚拟环境
python -m venv venv
source venv/bin/activate
pip install flask
```

### 5. 宝塔面板无法启动

**问题**: Python 项目启动失败

**解决方案**:

1. 检查 Python 版本是否 >= 3.7
2. 检查依赖是否完整安装
3. 查看项目日志，定位错误
4. 确保端口未被占用
5. 检查文件权限

### 6. Nginx 502 Bad Gateway

**问题**: 访问网站时出现 502 错误

**解决方案**:

1. 检查后端应用是否正常运行
2. 检查 Nginx 配置中的端口是否正确
3. 检查防火墙是否放行端口
4. 查看 Nginx 错误日志

### 7. Session 失效

**问题**: 用户频繁需要重新登录

**解决方案**:

1. 检查 `app.secret_key` 是否稳定
2. 检查浏览器 Cookie 设置
3. 检查服务器时间是否正确
4. 检查是否有多个应用实例

### 8. 性能优化

**建议**:

1. 使用 Gunicorn 或 uWSGI 替代 Flask 开发服务器
2. 配置适当的工作进程数（通常为 CPU 核心数 * 2 + 1）
3. 使用 Nginx 作为反向代理
4. 启用 gzip 压缩
5. 配置静态文件缓存
6. 考虑使用 PostgreSQL 或 MySQL 替代 SQLite（高并发场景）

## 备份与恢复

### 数据库备份

```bash
# 备份数据库
cp todos.db todos.db.backup.$(date +%Y%m%d)

# 或使用 SQLite 命令
sqlite3 todos.db ".backup todos.db.backup"
```

### 自动备份脚本

创建 `backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/path/to/backups"
DATE=$(date +%Y%m%d_%H%M%S)
cp /path/to/Todo-List/todos.db $BACKUP_DIR/todos.db.$DATE

# 保留最近 7 天的备份
find $BACKUP_DIR -name "todos.db.*" -mtime +7 -delete
```

添加到 crontab:

```bash
# 每天凌晨 2 点备份
0 2 * * * /path/to/backup.sh
```

### 数据恢复

```bash
# 停止应用
systemctl stop todo-app

# 恢复数据库
cp todos.db.backup todos.db

# 启动应用
systemctl start todo-app
```

## 监控与日志

### 应用日志

```bash
# Gunicorn 日志
tail -f /var/log/todo-app.out.log
tail -f /var/log/todo-app.err.log

# Nginx 日志
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

### 系统监控

推荐工具：
- **htop**: 系统资源监控
- **iotop**: I/O 监控
- **netstat**: 网络连接监控

## 安全建议

1. **修改默认密码**: 首次部署后立即修改管理员密码
2. **使用 HTTPS**: 配置 SSL 证书
3. **定期备份**: 设置自动备份
4. **更新依赖**: 定期更新 Flask 和其他依赖
5. **防火墙配置**: 只开放必要端口
6. **限制访问**: 使用 IP 白名单或 VPN
7. **日志监控**: 定期检查异常访问日志

## 技术支持

如遇到问题，请检查：
1. 应用日志
2. Nginx 日志
3. 系统日志
4. 本文档的常见问题部分

## 更新日志

- **v1.0**: 初始版本
- **v2.0**: 添加用户认证和管理后台
- **v2.1**: 添加部署文档