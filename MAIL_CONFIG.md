# 邮件通知服务配置指南

## 概述

待办事项应用支持邮件通知功能，会在每天 7:00-23:00 每小时向用户发送待办事项提醒邮件。

## 功能特性

- 定时发送：每小时检查一次，7:00-23:00 发送
- 智能过滤：只向有待办事项且未完成的用户发送邮件
- 美观模板：使用 HTML 格式的邮件模板
- 多邮箱支持：支持 QQ、163、Gmail 等主流邮箱

## 快速配置

### 1. 复制配置文件

```bash
cp .env.example .env
```

### 2. 编辑配置文件

编辑 `.env` 文件，填写你的邮箱配置：

```bash
# 启用邮件服务
MAIL_ENABLED=True

# SMTP 服务器配置
MAIL_SERVER=smtp.qq.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@qq.com
MAIL_PASSWORD=your-smtp-auth-code

# 发件人邮箱
MAIL_DEFAULT_SENDER=your-email@example.com
```

### 3. 重启应用

```bash
# Docker 部署
docker-compose restart

# 本地运行
python app.py
```

## 常用邮箱配置

### QQ邮箱

1. 登录 QQ 邮箱
2. 进入设置 → 账户
3. 开启 SMTP 服务
4. 生成授权码（不是 QQ 密码）
5. 配置：

```bash
MAIL_SERVER=smtp.qq.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-qq@qq.com
MAIL_PASSWORD=your-authorization-code
```

### 163邮箱

1. 登录 163 邮箱
2. 进入设置 → POP3/SMTP/IMAP
3. 开启 SMTP 服务
4. 获取授权密码
5. 配置：

```bash
MAIL_SERVER=smtp.163.com
MAIL_PORT=465
MAIL_USE_TLS=False
MAIL_USERNAME=your-email@163.com
MAIL_PASSWORD=your-authorization-password
```

### Gmail

1. 登录 Google 账户
2. 进入安全设置
3. 开启两步验证
4. 生成应用专用密码
5. 配置：

```bash
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

## 配置参数说明

| 参数 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| MAIL_ENABLED | 是否启用邮件服务 | True | True/False |
| MAIL_SERVER | SMTP 服务器地址 | smtp.qq.com | smtp.gmail.com |
| MAIL_PORT | SMTP 端口 | 587 | 587/465 |
| MAIL_USE_TLS | 是否使用 TLS 加密 | True | True/False |
| MAIL_USERNAME | 邮箱账号 | - | user@qq.com |
| MAIL_PASSWORD | 邮箱授权码 | - | 授权码 |
| MAIL_DEFAULT_SENDER | 发件人邮箱 | - | noreply@domain.com |

## 发送时间

系统会在每天 7:00-23:00 每小时检查并发送邮件：
- 每小时检查一次
- 只在 7:00-23:00 之间发送
- 只向有待办事项且未完成的用户发送
- 每个用户每天最多收到一封邮件

## 测试邮件配置

### 方法一：管理后台测试

1. 登录管理员账户
2. 进入管理后台
3. 点击"测试邮件"按钮
4. 输入测试邮箱地址
5. 点击发送

### 方法二：查看日志

启动应用后，查看控制台输出：

```
开始发送提醒邮件...
邮件已发送至: user@example.com
提醒邮件发送完成
```

## 故障排除

### 问题1：邮件发送失败

**症状**: 控制台显示 "邮件发送失败"

**解决方案**:
1. 检查邮箱账号授权码是否正确
2. 检查 SMTP 服务器地址和端口
3. 检查是否需要使用授权码而非密码
4. 检查防火墙是否阻止 SMTP 连接

### 问题2：未收到邮件

**症状**: 控制台显示发送成功，但未收到邮件

**解决方案**:
1. 检查垃圾邮件文件夹
2. 检查发件人邮箱是否被标记为垃圾邮件
3. 尝试使用其他邮箱服务
4. 检查收件人邮箱地址是否正确

### 问题3：定时任务不执行

**症状**: 到了指定时间但未收到邮件

**解决方案**:
1. 检查 `MAIL_ENABLED` 是否为 `True`
2. 检查服务器时间是否正确（使用北京时间）
3. 查看应用日志，确认定时任务已启动
4. 确认用户邮箱地址已填写

## 安全建议

1. **使用授权码**: 不要使用邮箱登录密码，使用授权码
2. **环境变量**: 将敏感信息存储在环境变量中
3. **定期更换**: 定期更换 SMTP 授权码
4. **监控日志**: 定期检查邮件发送日志

## 禁用邮件服务

如果不需要邮件通知功能，可以禁用：

```bash
# 在 .env 文件中
MAIL_ENABLED=False
```

或在 `config.py` 中设置：

```python
MAIL_ENABLED = False
```

## 邮件模板

邮件模板包含以下内容：

- 用户名问候
- 当前日期
- 未完成待办事项数量
- 待办事项列表
- 应用访问链接
- 美观的 HTML 样式

## 技术支持

如遇到问题，请检查：
1. `.env` 配置是否正确
2. 邮箱 SMTP 服务是否已开启
3. 应用日志中的错误信息
4. 邮箱的垃圾邮件文件夹
