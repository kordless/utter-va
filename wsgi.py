# wsgi setup
import sys
sys.path.insert(0, '/var/www/utterio/')
from webapp import app as application
