#!/usr/bin/python
# manage.py
# -*- encoding:utf-8 -*-
import os, sys, socket, json
from urllib2 import urlopen
from flask import Flask
from flaskext.actions import Manager
from webapp import app, db
from webapp.configure.models import OpenStack, Appliance
from webapp.api.models import Images, Flavors
from webapp.users.models import User

app.config.from_object('config.DebugConfiguration') # configuration
manager = Manager(app, default_help_actions=False)

def configure_blurb():
	hostname = socket.gethostname()
	IP = socket.gethostbyname(hostname)
	print "Visit http://%s/ to setup your appliance." % IP

def server_connect( method = "version" ):
	appliance = db.session.query(Appliance).first()
	url = app.config['APP_WEBSITE'] + 'api/%s?ver=' % method + app.config['VERSION'] + '&apitoken=' + appliance.apitoken
	response = urlopen(url, timeout=10).read()
	return json.loads(response)

def sync(app):
	def action():
		# check version of virtual appliance
		version = False
		try:
			version = server_connect( method = "version" )
		except AttributeError as ex:
			configure_blurb()
		except IOError as ex:
			print "Can't contact central server.  Try again later."
		except ValueError as ex:
			print "Having issues parsing JSON from the site: %s.  Open a ticket." % type(ex).__name__
		except Exception as ex:
			print "An error of type %s has occured.  Open a ticket." % type(ex).__name__
		
		if not version:
			return action
		
		# update list of current images in db
		remoteimages = False
		try:
			remoteimages = server_connect("images")
		except AttributeError as ex:
			configure_blurb()
		except IOError as ex:
			print "Can't contact central server.  Try again later."
		except ValueError as ex:
			print "Having issues parsing JSON from the site: %s.  Open a ticket." % type(ex).__name__
		except Exception as ex:
			print "An error of type %s has occured.  Open a ticket." % type(ex).__name__

		if not remoteimages:
			return action

		# update images from server
		images = Images()
		images.sync(remoteimages)

		# update list of current flavors in db
		remoteflavors = False
		try:
			remoteflavors = server_connect("flavors")
		except AttributeError as ex:
			configure_blurb()
		except IOError as ex:
			print "Can't contact central server.  Try again later."
		except ValueError as ex:
			print "Having issues parsing JSON from the site: %s.  Open a ticket." % type(ex).__name__
		except Exception as ex:
			print "An error of type %s has occured.  Open a ticket." % type(ex).__name__

		if not remoteflavors:
			return action

		# update flavors from server
		flavors = Flavors()
		flavors.sync(remoteflavors)

	return action

def reset(app):
	def action():
		# run database reset script
		os.system('./resetdb.sh')

		# update appliance database
		appliance = db.session.query(Appliance).first()
		
		if not appliance:
			appliance = Appliance()

		appliance.initialize()
		appliance.update(appliance)
		db.session.commit()

		print "The database has been cleared and a new API token has been generated."
		configure_blurb()
	return action

def serve(app):
	def action():
		from werkzeug import SharedDataMiddleware

		# add static directory to be served by development server
		app.wsgi_app = SharedDataMiddleware(app.wsgi_app, {'/': os.path.join(os.path.dirname(__file__), './webapp/static') })
		app.run(debug=True, host="0.0.0.0")
		sys.exit()
	return action


manager.add_action('sync', sync)
manager.add_action('reset', reset)
manager.add_action('serve', serve)

if __name__ == "__main__":
	manager.run()
