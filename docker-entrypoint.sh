#!/bin/sh
# 容器入口：修复首次挂载导致的 todos.db 目录问题，并以非 root 用户启动服务
set -e

if [ -d /app/todos.db ]; then
    echo "检测到 /app/todos.db 是目录（首次 bind mount 常见），已删除并改为文件"
    rm -rf /app/todos.db
fi

mkdir -p /app/flask_session
touch /app/todos.db
chown app:app /app/todos.db 2>/dev/null || true
chown -R app:app /app/flask_session 2>/dev/null || true

exec gosu app "$@"
