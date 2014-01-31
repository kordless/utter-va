import os
import shellconfig

_basedir = os.path.abspath(os.path.dirname(__file__))


class BaseConfiguration(object):

	# Pool Customization
	POOL_NAME = "StackMonkey"
	POOL_NAME_LOWER = ''.join(POOL_NAME.split()).lower()
	POOL_WEBSITE = "http://www.stackmonkey.com/".strip("/")
	POOL_TWITTER_HANDLE = "stackape"
	POOL_TWITTER_NAME = POOL_NAME
	POOL_LINKEDIN_HANDLE = POOL_NAME_LOWER
	POOL_LINKEDIN_NAME = POOL_NAME
	POOL_GPLUS_HANDLE = POOL_NAME_LOWER
	POOL_GPLUS_NAME = POOL_NAME
	# End Pool Customization

	DEBUG = False
	TESTING = False

	VERSION = "0.1.0"
	APP_NAME = "%s Virtual Appliance" % POOL_NAME
	APP_WEBSITE = POOL_WEBSITE
	APP_IRC_URL = "http://mibbit.com/?channel=#%s&server=irc.mibbit.net" % POOL_NAME_LOWER
	
	DATABASE = "xoviova.db"
	DATABASE_PATH = os.path.join(_basedir, DATABASE)
	SQLALCHEMY_DATABASE_URI = 'sqlite:///' + DATABASE_PATH
	
	SECRET_KEY = "13afa9bb8b142d99b78bc143f754f736"
	
	CSRF_ENABLED = True
	CSRF_SESSION_KEY = "d41d8cd98f00b204e9800998ecf8427e"
	
	THREADS_PER_PAGE = 8

# currently not used - revise
class TestConfiguration(BaseConfiguration):
	TESTING = True
	APP_WEBSITE = "http://127.0.0.1:8080/".strip("/")
	DATABASE = 'test.db'
	DATABASE_PATH = os.path.join(_basedir, DATABASE)
	SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'  # + DATABASE_PATH

	CSRF_ENABLED = False


class DebugConfiguration(BaseConfiguration):
	DEBUG = True
	APP_WEBSITE = "http://127.0.0.1:8080/".strip("/")