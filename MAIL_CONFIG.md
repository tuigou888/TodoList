# 邮件通知服务配置指南

## 概述

待办事项应用支持邮件通知功能，会在每天指定时间（默认为凌晨0点）向用户发送待办事项提醒邮件。

## 功能特性

- 定时发送：每小时检查一次，仅在指定整点发送
- 智能过滤：只向有待办事项的用户发送邮件
- 美观模板：使用HTML格式的邮件模板
- 多邮箱支持：支持QQ、163、Gmail等主流邮箱

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
MAIL_PASSWORD=your-smtp-password
MAIL_DEFAULT_SENDER=noreply@todoapp.com

# 提醒时间（0-23）
MAIL_REMINDER_HOUR=0
```

### 3. 重启应用

```bash
# 停止应用
# Ctrl+C 或 systemctl stop todo-app

# 重新启动
python app.py
# 或
systemctl start todo-app
```

## 常用邮箱配置

### QQ邮箱

1. 登录QQ邮箱
2. 进入设置 → 账户
3. 开启SMTP服务
4. 生成授权码（不是QQ密码）
5. 配置：

```bash
MAIL_SERVER=smtp.qq.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-qq-number@qq.com
MAIL_PASSWORD=your-authorization-code
```

### 163邮箱

1. 登录163邮箱
2. 进入设置 → POP3/SMTP/IMAP
3. 开启SMTP服务
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

1. 登录Google账户
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

### 126邮箱

```bash
MAIL_SERVER=smtp.126.com
MAIL_PORT=465
MAIL_USE_TLS=False
MAIL_USERNAME=your-email@126.com
MAIL_PASSWORD=your-smtp-password
```

## 配置参数说明

| 参数 | 说明 | 默认值 | 示例 |
|------|------|---------|--------|
| MAIL_ENABLED | 是否启用邮件服务 | True | True/False |
| MAIL_SERVER | SMTP服务器地址 | smtp.qq.com | smtp.gmail.com |
| MAIL_PORT | SMTP端口 | 587 | 587/465 |
| MAIL_USE_TLS | 是否使用TLS加密 | True | True/False |
| MAIL_USERNAME | 邮箱账号 | - | user@qq.com |
| MAIL_PASSWORD | 邮箱密码/授权码 | - | 授权码 |
| MAIL_DEFAULT_SENDER | 发件人邮箱 | noreply@todoapp.com | noreply@domain.com |
| MAIL_REMINDER_HOUR | 提醒时间（小时） | 0 | 0-23 |

## 提醒时间设置

`MAIL_REMINDER_HOUR` 参数控制每天发送邮件的时间：

- `0` = 凌晨0点（默认）
- `9` = 上午9点
- `12` = 中午12点
- `18` = 下午6点

**注意**: 系统使用服务器时间，请根据需要调整。

## 测试邮件配置

### 方法一：查看日志

启动应用后，查看控制台输出：

```bash
python app.py
```

会看到类似输出：
```
邮件提醒定时任务已启动
开始发送提醒邮件...
邮件已发送至: user@example.com
提醒邮件发送完成
```

### 方法二：手动触发

修改 `app.py` 中的 `send_reminder_emails()` 函数，临时修改时间判断：

```python
if current_hour != Config.MAIL_REMINDER_HOUR:
    # 临时注释掉这行，用于测试
    # conn.close()
    # return
```

重启应用即可立即发送邮件。

## 邮件模板

邮件模板包含以下内容：

- 用户名问候
- 当前日期
- 未完成待办事项数量
- 待办事项列表
- 应用访问链接
- 美观的HTML样式

## 故障排除

### 问题1：邮件发送失败

**症状**: 控制台显示 "邮件发送失败"

**解决方案**:
1. 检查邮箱账号密码是否正确
2. 检查SMTP服务器地址和端口
3. 检查是否需要使用授权码而非密码
4. 检查防火墙是否阻止SMTP连接

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
2. 检查 `MAIL_REMINDER_HOUR` 设置是否正确
3. 检查服务器时间是否正确
4. 查看应用日志，确认定时任务已启动

### 问题4：端口被占用

**症状**: SMTP连接失败

**解决方案**:
1. 检查网络连接
2. 尝试使用其他端口（465/587）
3. 联系邮箱服务商确认SMTP设置

## 安全建议

1. **使用授权码**: 不要使用邮箱登录密码，使用授权码
2. **环境变量**: 将敏感信息存储在环境变量中
3. **定期更换**: 定期更换SMTP密码
4. **限制访问**: 只允许特定IP访问SMTP
5. **监控日志**: 定期检查邮件发送日志

## 生产环境部署

### 使用环境变量

在生产环境中，建议使用系统环境变量：

```bash
# Linux/macOS
export MAIL_ENABLED=True
export MAIL_SERVER=smtp.qq.com
export MAIL_USERNAME=your-email@qq.com
export MAIL_PASSWORD=your-password

# Windows PowerShell
$env:MAIL_ENABLED="True"
$env:MAIL_SERVER="smtp.qq.com"
$env:MAIL_USERNAME="your-email@qq.com"
$env:MAIL_PASSWORD="your-password"
```

### 使用 .env 文件

1. 确保不将 `.env` 文件提交到版本控制
2. 在 `.gitignore` 中添加 `.env`
3. 设置正确的文件权限：

```bash
chmod 600 .env
```

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

## 邮件发送频率

- 定时任务每小时检查一次
- 只在指定整点发送邮件
- 只向有待办事项的用户发送
- 每个用户每天最多收到一封邮件

## 技术支持

如遇到问题，请检查：
1. `.env` 配置是否正确
2. 邮箱SMTP服务是否已开启
3. 应用日志中的错误信息
4. 邮箱的垃圾邮件文件夹

## 更新日志

- **v1.0**: 初始版本，支持基础邮件通知