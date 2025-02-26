# Gunicorn配置文件
timeout = 300  # 设置为5分钟超时
workers = 4
threads = 2
bind = "0.0.0.0:5001" 