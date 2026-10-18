# 邮件通知服务配置指南

## 概述

待办事项应用支持每日提醒邮件。提醒时间由**每个用户**在「设置」页单独配置（默认 09:00），并可随时关闭。调度器每分钟检查一次，同一用户每天最多发送一封。

此外还支持**每日回顾**与**每周回顾**（每周一发送），内容包括完成/未完成/逾期、今日三件事与本周趋势。

## 功能特性

- 按用户配置的 `reminder_time` 发送，每天最多一封
- 只向存在未完成待办、且邮箱不为空的用户发送
- 支持 465 端口 SSL 直连与 587 端口 STARTTLS
- SMTP 连接/读写超时（默认 15 秒），避免阻塞请求线程
- 邮件正文对用户名、待办标题做 HTML 转义
- 邮件中的链接使用 `BASE_URL`，可正确指向生产域名
- 设置页可「立即发送一次」，60 秒内限一次

## 快速配置

### 1. 复制配置文件

```bash
cp .env.example .env
```

### 2. 编辑 `.env`

```bash
# 站点地址（邮件里的链接）
BASE_URL=https://todo.example.com

# 启用邮件服务
MAIL_ENABLED=True

# SMTP 服务器（QQ 邮箱示例，STARTTLS 587）
MAIL_SERVER=smtp.qq.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USE_SSL=False
MAIL_TIMEOUT=15
MAIL_USERNAME=your-email@qq.com
MAIL_PASSWORD=your-smtp-auth-code
MAIL_DEFAULT_SENDER=your-email@qq.com
```

### 3. 重启应用

```bash
docker-compose restart   # Docker
python app.py            # 本地
```

## 常用邮箱配置

### QQ 邮箱（STARTTLS 587）

1. 登录 QQ 邮箱 → 设置 → 账户
2. 开启 SMTP 服务
3. 生成授权码（不是 QQ 密码）
4. 配置：

```bash
MAIL_SERVER=smtp.qq.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USE_SSL=False
MAIL_USERNAME=your-qq@qq.com
MAIL_PASSWORD=your-authorization-code
```

### 163 / 126 邮箱（SSL 465）

```bash
MAIL_SERVER=smtp.163.com
MAIL_PORT=465
MAIL_USE_TLS=False        # 关键：465 端口不要用 STARTTLS
MAIL_USE_SSL=True         # 关键：使用 SSL 直连
MAIL_USERNAME=your-email@163.com
MAIL_PASSWORD=your-authorization-password
```

### Gmail（STARTTLS 587）

```bash
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USE_SSL=False
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

## 配置参数说明

| 参数 | 说明 | 默认值 | 示例 |
| --- | --- | --- | --- |
| `MAIL_ENABLED` | 是否启用邮件服务 | `True` | `True` / `False` |
| `MAIL_SERVER` | SMTP 服务器地址 | `smtp.qq.com` | `smtp.gmail.com` |
| `MAIL_PORT` | SMTP 端口 | `587` | `587` / `465` |
| `MAIL_USE_TLS` | 是否使用 STARTTLS（587） | `True` | `True` / `False` |
| `MAIL_USE_SSL` | 是否使用 SSL 直连（465） | `False` | `True` / `False` |
| `MAIL_TIMEOUT` | 连接/读写超时（秒） | `15` | `10` |
| `MAIL_USERNAME` | 邮箱账号 | 空 | `user@qq.com` |
| `MAIL_PASSWORD` | 邮箱授权码 | 空 | 授权码 |
| `MAIL_DEFAULT_SENDER` | 发件人邮箱 | `noreply@todoapp.com` | `user@qq.com` |
| `BASE_URL` | 邮件链接的站点地址 | `http://localhost:5145` | `https://todo.example.com` |

> 旧配置 `MAIL_REMINDER_HOUR` 已废弃；现在按每个用户在设置页配置的时间发送。

## 用户提醒设置

登录后进入 `/settings`：

1. 勾选/取消「启用每日提醒邮件」
2. 选择提醒时间（24 小时制）
3. 点击「保存设置」
4. 可点击「立即发送一次」验证邮件链路

调度器按以下规则发送：

- 每分钟检查一次
- 当前时间 ≥ 用户提醒时间，且 `last_reminded_on` 不是今天
- 用户启用提醒、邮箱非空、存在未完成待办
- 在数据库中原子占位 `last_reminded_on`，多 worker 下不会重复发送

## 回顾邮件

- **每日回顾**：在设置页开启「每日回顾」，到达设定时间后发送当天完成/未完成/逾期与今日三件事。
- **每周回顾**：每周一同一时间发送本周完成、新增、完成率与最久未完成任务。
- 两者都复用邮件 outbox 队列，失败会按 1/5/15 分钟退避重试；可在设置页「立即发送回顾」测试。
- 关闭每日提醒不会关闭回顾；两者独立开关。

## 测试邮件配置

### 方法一：管理后台

1. 管理员登录 → `/admin`
2. 点击「测试邮件」
3. 输入收件邮箱并发送

### 方法二：设置页

1. 用户登录 → `/settings`
2. 点击「立即发送一次」

### 方法三：查看日志

```text
每日提醒调度器已启动（每分钟检查一次）
已发送 1 封每日提醒
```

邮件地址只会在 DEBUG 级别记录，INFO 日志不包含收件人邮箱。

## 故障排除

### 问题1：邮件发送失败

**症状**：日志出现 `邮件发送失败`

**排查**：
1. 确认使用授权码而非邮箱登录密码
2. 确认端口与加密方式匹配：465 → `MAIL_USE_SSL=True`、`MAIL_USE_TLS=False`；587 → `MAIL_USE_TLS=True`
3. 检查服务器出站 465/587 端口是否被防火墙阻止
4. 检查 `MAIL_USERNAME` / `MAIL_PASSWORD` 是否为空

### 问题2：未收到邮件

**排查**：
1. 检查垃圾邮件文件夹
2. 确认用户邮箱已填写且格式正确
3. 确认 `MAIL_ENABLED=True`
4. 确认有未完成待办（没有待办时不会发送）
5. 确认 `last_reminded_on` 不是今天（数据库）

### 问题3：提醒时间到了但没发

**排查**：
1. 检查用户是否关闭了每日提醒（`reminder_enabled`）
2. 检查服务器时间与用户设置的时区是否一致（Docker 默认 `Asia/Shanghai`）
3. 查看日志中调度器是否启动
4. 本地 `python app.py` 的 debug reloader 只在工作子进程启动调度器

### 问题4：点击「立即发送」提示操作频繁

手动提醒有 60 秒最小间隔，稍后再试即可。

## 安全建议

1. 使用邮箱授权码，不要使用登录密码
2. 敏感信息只放在 `.env`，不要提交到 Git
3. 定期更换 SMTP 授权码
4. 生产环境设置 `BASE_URL` 为 HTTPS 域名
5. 定期检查邮件发送日志与失败率

## 禁用邮件服务

```bash
# .env
MAIL_ENABLED=False
```

禁用后定时任务与「立即发送」都会直接返回，不会建立 SMTP 连接。

## 邮件模板

提醒邮件包含：

- 用户名问候
- 当前时间与用户的每日提醒时间
- 未完成待办数量与列表（标题、创建时间、已过去时间）
- 查看待办与设置页链接
- 响应式 HTML 样式

所有用户输入在拼接 HTML 前都会转义。
