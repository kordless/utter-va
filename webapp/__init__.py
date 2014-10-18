import os

# stackmonkey approved monkey patch
import gevent.monkey; gevent.monkey.patch_thread()

from flask import Flask, request, Request, render_template, send_from_directory
from flask.ext.seasurf import SeaSurf
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager, current_user
from flask.ext.actions import Manager
from flask.ext.bcrypt import Bcrypt
from flask.ext.socketio import SocketIO

# handle SSL termination through ngrok
class ProxiedRequest(Request):
    def __init__(self, environ, populate_request=True, shallow=False):
        super(Request, self).__init__(environ, populate_request, shallow)
        
        if self.headers.get('X-Forwarded-Proto') == 'https':
        	environ['wsgi.url_scheme'] = 'https'
            
# app setup + static files
app = Flask(__name__, static_url_path='', static_folder='static')
socketio = SocketIO(app)

# csrf_token protect
csrf = SeaSurf(app)

# apply SSL termination handling
app.request_class = ProxiedRequest

# configuration file
if os.path.isfile('./DEV'): 
	app.config.from_object('config.DebugConfiguration')
else:
	app.config.from_object('config.BaseConfiguration')

# other app'ish things
login_manager = LoginManager(app) # login manager
manager = Manager(app) # shell actions manager
db = SQLAlchemy(app) # database connection
bcrypt = Bcrypt(app) # hashing function

from webapp.models.instances import Instances

# users module blueprint
from webapp.handlers.userhandlers import mod as usersModule
app.register_blueprint(usersModule)

# configure module blueprint
from webapp.handlers.configurehandlers import mod as configureModule
app.register_blueprint(configureModule)

# api module blueprint
from webapp.handlers.apihandlers import mod as APIModule
app.register_blueprint(APIModule)

# socket module blueprint
from webapp.handlers.sockethandlers import mod as socketModule
app.register_blueprint(socketModule)

#add our view as the login view
login_manager.login_view = "users.login"

#----------------------------------------
# controllers
#----------------------------------------

@app.route('/favicon.ico')
def favicon():
	return send_from_directory(os.path.join(app.root_path, 'static'), 'img/favicon.ico')

@app.route("/", methods=['GET'])
def index():
	return render_template('index.html')

@app.errorhandler(404)
def page_not_found(e):
	return render_template('404.html'), 404

@app.errorhandler(400)
def key_error(e):
	app.logger.warning('Invalid request resulted in KeyError.', exc_info=e)
	return render_template('400.html'), 400

@app.errorhandler(500)
def internal_server_error(e):
	app.logger.warning('An unhandled exception is being displayed to the end user.', exc_info=e)
	return render_template('generic.html'), 500

@app.errorhandler(Exception)
def unhandled_exception(e):
	app.logger.error('An unhandled exception is being displayed to the end user.', exc_info=e)
	return render_template('generic.html'), 500

@app.before_request
def log_entry():
	app.logger.debug("Handling request.")

@app.teardown_request
def log_exit(exc):
	app.logger.debug("Finished handling request.", exc_info=exc)

# manager logs
import logging
from logging.handlers import RotatingFileHandler

# delete existing handlers
del app.logger.handlers[:]
handler = RotatingFileHandler('%s/../logs/utter.log' % os.path.dirname(os.path.realpath(__file__)), maxBytes=1000000, backupCount=7)
handler.setLevel(logging.INFO)
log_format = "%(asctime)s - %(levelname)s - %(message)s"
formatter = logging.Formatter(log_format)
handler.setFormatter(formatter)
app.logger.addHandler(handler)


