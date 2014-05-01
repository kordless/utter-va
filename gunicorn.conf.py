import os
import multiprocessing

# check if we are running with DEV
if os.path.isfile('./DEV'):
  bind = '0.0.0.0:5000'
  daemon = False
  loglevel = 'debug'
  errorlog = '-'
  accesslog = '-'
else:
  bind = '0.0.0.0:80'
  daemon = True
  loglevel = 'info'
  errorlog = './log/error.log'
  accesslog = './log/access.log'

# other settings
backlog = 1024 
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync '
worker_connections = 1000
timeout = 30
keepalive = 2
debug = False
spew = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = '/tmp'
