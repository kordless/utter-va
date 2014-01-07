import os

_basedir = os.path.abspath(os.path.dirname(__file__))


class BaseConfiguration(object):
	DEBUG = False
	TESTING = False

	APP_NAME = "Stackmonkey Virtual Appliance"
	APP_WEBSITE = "http://stackmonkey.com"
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

	CSRF_ENABLED = False

	DATABASE = 'test.db'
	DATABASE_PATH = os.path.join(_basedir, DATABASE)
	SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'  # + DATABASE_PATH


class DebugConfiguration(BaseConfiguration):
	DEBUG = True
