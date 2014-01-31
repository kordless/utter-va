# wsgi setup
import sys
sys.path.insert(0, '/var/www/xoviova/')
from webapp import app as application
