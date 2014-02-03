#!/usr/bin/python
# manage.py
# -*- encoding:utf-8 -*-
import os
import sys
import json
import yaml

from subprocess import Popen
from urllib2 import urlopen
from flask import Flask
from flaskext.actions import Manager

from webapp import app, db
from webapp.configure.models import Appliance, OpenStack
from webapp.api.models import Images, Flavors
from webapp.libs.utils import configure_blurb, query_yes_no

# configuration file
if os.path.isfile('./DEV'): 
	app.config.from_object('config.DebugConfiguration')
else:
	app.config.from_object('config.BaseConfiguration')

# manager handler
manager = Manager(app, default_help_actions=False)

def sync(app):
	def action():
		# get the appliance configuration
		appliance = db.session.query(Appliance).first()
		
		if not appliance:
			configure_blurb()

		# grab remote pool's flavors and images
		images = Images()
		response = images.sync(appliance.apitoken)

		flavors = Flavors()
		response = flavors.sync(appliance.apitoken)

	return action

# reset the entire system
def reset(app):
	def action():
		try:
			if query_yes_no("Are you sure you want to reset the appliance?"):

				# run database reset script - use current path to run file
				path = os.path.dirname(os.path.abspath(__file__))
				os.system('%s/resetdb.sh %s/' % (path, path))

				# initialize the appliance object
				appliance = Appliance()
				appliance.initialize()
				
				# sync to remote database
				images = Images()
				response = images.sync(appliance.apitoken)

				flavors = Flavors()
				response = flavors.sync(appliance.apitoken)

				if response['response'] == "success":
					print "The database has been cleared and a new API token has been generated."
					configure_blurb()
				else:
					print response['response']

		except ValueError as ex:
			print ex

	return action

# development server
def serve(app):
	def action():
		from werkzeug import SharedDataMiddleware

		# add static directory to be served by development server
		app.wsgi_app = SharedDataMiddleware(
			app.wsgi_app, 
			{'/': os.path.join(os.path.dirname(__file__), './webapp/static') }
		)
		app.run(debug=True, host="0.0.0.0")
		sys.exit()
	
	return action

def install(app):
	def action():
		# run database reset script - use current path to run file
		path = os.path.dirname(os.path.abspath(__file__))
		os.system('%s/resetdb.sh %s/' % (path, path))

		# initialize the appliance object
		appliance = Appliance()
		appliance.initialize()
		
		# sync to remote database
		images = Images()
		response = images.sync(appliance.apitoken)

		flavors = Flavors()
		response = flavors.sync(appliance.apitoken)

		# configure output
		configure_blurb()
		
	return action

def tunnel(app):
	def action():
		# get the appliance configuration
		appliance = db.session.query(Appliance).first()

		if appliance.ngroktoken and appliance.paymentaddress:
			appliance.build_tunnel_conf()		
		else:
			configure_blurb()

	return action

def clean(app):
	def action():
		path = os.path.dirname(os.path.abspath(__file__))
		os.system('rm tunnel.conf.*')
	return action


# command line commands
manager.add_action('sync', sync)
manager.add_action('reset', reset)
manager.add_action('serve', serve)
manager.add_action('install', install)
manager.add_action('tunnel', tunnel)
manager.add_action('clean', clean)

if __name__ == "__main__":
	manager.run()
