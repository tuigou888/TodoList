"""
Gunicorn 配置文件
用于配置 Gunicorn 服务器和启动钩子
"""

import os
import sys

# 添加应用目录到路径
sys.path.insert(0, '/app')

# 服务器配置
bind = "0.0.0.0:5145"
workers = 4
timeout = 120

# 日志配置
accesslog = "-"
errorlog = "-"
loglevel = "info"


def on_starting(server):
    """
    Gunicorn 启动时调用（主进程）
    用于初始化数据库和启动定时任务
    """
    print("=" * 50)
    print("Gunicorn 正在启动...")
    print("=" * 50)


def when_ready(server):
    """
    Gunicorn 准备好接受请求时调用
    在工作进程启动后执行
    """
    print("=" * 50)
    print("Gunicorn 已就绪，正在启动定时任务...")
    print("=" * 50)
    
    # 导入应用模块
    from app import init_db, start_reminder_scheduler
    
    # 初始化数据库
    try:
        init_db()
        print("✓ 数据库初始化完成")
    except Exception as e:
        print(f"✗ 数据库初始化失败: {e}")
    
    # 启动定时任务
    try:
        start_reminder_scheduler()
        print("✓ 定时任务启动完成")
    except Exception as e:
        print(f"✗ 定时任务启动失败: {e}")


def worker_int(worker):
    """工作进程接收到 SIGINT 或 SIGQUIT 时调用"""
    print(f"工作进程 {worker.pid} 正在关闭...")


def on_exit(server):
    """Gunicorn 关闭时调用"""
    print("=" * 50)
    print("Gunicorn 正在关闭...")
    print("=" * 50)
