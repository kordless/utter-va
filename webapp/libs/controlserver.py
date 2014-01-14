import os, sys, socket, json
from urllib2 import urlopen
from webapp import app, db
from webapp.configure.models import OpenStack, Appliance

def configure_blurb():
	hostname = socket.gethostname()
	IP = socket.gethostbyname(hostname)
	print "Visit http://%s/ to setup your appliance before running this command." % IP

def check_version():
	# check our version
	appliance = db.session.query(Appliance).first()
	
	# contact server and ask if we have a good version
	try:
		url = app.config['APP_WEBSITE'] + 'api/version?ver=' + app.config['VERSION'] + '&apikey=' + appliance.apikey
		response = urlopen(url, timeout=10).read()
		version = json.loads(response)
		return True
		# add the code to check the version here
	except AttributeError as ex:
		configure_blurb()
	except IOError as ex:
		print "Can't contact central server.  Try again later."
	except Exception as ex:
		print "An error of type %s has occured.  Open a ticket." % type(ex).__name__
	
	return False

def get_images():
	# get image list from server
	appliance = db.session.query(Appliance).first()

	try:
		url = app.config['APP_WEBSITE'] + 'api/images?ver=' + app.config['VERSION'] + '&apikey=' + appliance.apikey
		response = urlopen(url, timeout=10).read()
		images = json.loads(response)
		return images
	except AttributeError as ex:
		configure_blurb()
	except IOError as ex:
		print "Can't contact central server.  Try again later."
	except ValueError as ex:
		print "Having issues parsing JSON from the site: %s.  Open a ticket." % type(ex).__name__
	except Exception as ex:
		print "An error of type %s has occured.  Open a ticket." % type(ex).__name__

def get_flavors():
	# get image list from server
	appliance = db.session.query(Appliance).first()

	try:
		url = app.config['APP_WEBSITE'] + 'api/flavors?ver=' + app.config['VERSION'] + '&apikey=' + appliance.apikey
		response = urlopen(url, timeout=10).read()
		flavors = json.loads(response)
		return flavors
	except AttributeError as ex:
		configure_blurb()
	except IOError as ex:
		print "Can't contact central server.  Try again later."
	except ValueError as ex:
		print "Having issues parsing JSON from the site: %s.  Open a ticket." % type(ex).__name__
	except Exception as ex:
		print "An error of type %s has occured.  Open a ticket." % type(ex).__name__

