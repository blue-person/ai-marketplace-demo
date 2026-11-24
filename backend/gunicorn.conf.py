# Application server for the backend (replaces the Flask development server).
bind = "0.0.0.0:8000"
workers = 2
threads = 2
timeout = 30
accesslog = "-"
errorlog = "-"
loglevel = "info"
