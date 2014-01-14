import os

_basedir = os.path.abspath(os.path.dirname(__file__))


class BaseConfiguration(object):
	DEBUG = False
	TESTING = False

	VERSION = "0.1.0"
	APP_NAME = "Electorum Virtual Appliance"
	APP_WEBSITE = "https://electorums.appspot.com/"
	# APP_WEBSITE = "https://1.2.3.4/"
	APP_IRC_URL = "http://mibbit.com/?channel=%23stackmonkey&server=irc.mibbit.net"
	
	DATABASE = "stackmonkey.db"
	DATABASE_PATH = os.path.join(_basedir, DATABASE)
	SQLALCHEMY_DATABASE_URI = 'sqlite:///' + DATABASE_PATH
	
	SECRET_KEY = "13afa9bb8b142d99b78bc143f754f736"
	
	CSRF_ENABLED = True
	CSRF_SESSION_KEY = "d41d8cd98f00b204e9800998ecf8427e"
	
	THREADS_PER_PAGE = 8


class TestConfiguration(BaseConfiguration):
	TESTING = True
	APP_WEBSITE = "http://127.0.0.1:8080/"
	DATABASE = 'test.db'
	DATABASE_PATH = os.path.join(_basedir, DATABASE)
	SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'  # + DATABASE_PATH

	CSRF_ENABLED = False


class DebugConfiguration(BaseConfiguration):
	DEBUG = True
	APP_WEBSITE = "http://127.0.0.1:8080/"