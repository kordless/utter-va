#!/usr/bin/python
# manage.py
# -*- encoding:utf-8 -*-
import os, sys, socket, json
from urllib2 import urlopen
from flask import Flask
from flaskext.actions import Manager
from webapp import app, db
from webapp.libs.utils import sync_remote
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
	url = app.config['APP_WEBSITE'] + '/api/%s?ver=%s&apitoken=%s' % (method, app.config['VERSION'], appliance.apitoken)
	response = urlopen(url, timeout=10).read()
	return json.loads(response)

def sync(app):
	def action():
		# grab remote pool's flavors and images
		sync_remote()

	return action

def reset(app):
	def action():
		# run database reset script
		os.system('./resetdb.sh')

		# update appliance database
		appliance = db.session.query(Appliance).first()
		
		if not appliance:
			appliance = Appliance()

		# initialize the appliance object
		appliance.initialize()
		appliance.update(appliance)
		db.session.commit()
		
		# sync to remote database
		result = sync_remote(appliance.apitoken)

		if result['response'] == "success":
			print "The database has been cleared and a new API token has been generated."
			configure_blurb()
		else:
			print result['response']

	return action

def serve(app):
	def action():
		from werkzeug import SharedDataMiddleware

		# add static directory to be served by development server
		app.wsgi_app = SharedDataMiddleware(app.wsgi_app, {'/': os.path.join(os.path.dirname(__file__), './webapp/static') })
		app.run(debug=False, host="0.0.0.0")
		sys.exit()
	
	return action


manager.add_action('sync', sync)
manager.add_action('reset', reset)
manager.add_action('serve', serve)

if __name__ == "__main__":
	manager.run()
