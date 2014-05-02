import os
import multiprocessing

# check if we are running with DEV
if os.path.isfile('./DEV'):
  bind = '0.0.0.0:5000'
  daemon = False
  loglevel = 'debug'
  errorlog = '-'
  accesslog = '-'
  debug = True
  workers = 1
else:
  bind = '0.0.0.0:80'
  daemon = True
  loglevel = 'info'
  errorlog = './logs/error.log'
  accesslog = './logs/access.log'
  debug = False
  workers = 1

# other settings
worker_class = 'socketio.sgunicorn.GeventSocketIOWorker'
timeout = 30
pidfile = '/tmp/gunicorn.pid'
umask = 0
user = None
group = None
tmp_upload_dir = '/tmp'
