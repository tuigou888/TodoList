import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')
    
    # CORS 跨域配置
    CORS_ENABLED = os.environ.get('CORS_ENABLED', 'True').lower() in ['true', '1', 't']
    # 允许的域名，多个用逗号分隔
    ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:3000,http://localhost:5000,http://127.0.0.1:3000,http://127.0.0.1:5000').split(',')
    
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.qq.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() in ['true', '1', 't']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@todoapp.com')
    
    MAIL_ENABLED = os.environ.get('MAIL_ENABLED', 'True').lower() in ['true', '1', 't']
    
    MAIL_REMINDER_HOUR = int(os.environ.get('MAIL_REMINDER_HOUR', 0))