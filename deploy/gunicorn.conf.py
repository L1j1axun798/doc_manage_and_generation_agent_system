bind = "unix:/run/wind-doc-system/gunicorn.sock"
umask = 0o007
workers = 3
worker_class = "gthread"
threads = 4
timeout = 120
graceful_timeout = 30
keepalive = 5
accesslog = "/var/log/wind-doc-system/gunicorn-access.log"
errorlog = "/var/log/wind-doc-system/gunicorn-error.log"
access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s '
    'host="%({host}i)s" xff="%({x-forwarded-for}i)s" '
    'xproto="%({x-forwarded-proto}i)s" connection="%({connection}i)s" '
    'agent="%({user-agent}i)s"'
)
capture_output = True
