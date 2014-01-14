# manage.py
# -*- encoding:utf-8 -*-
import os, sys, socket
from urllib2 import urlopen
from flask import Flask
from flaskext.actions import Manager
from webapp import app, db
from webapp.configure.models import OpenStack, Appliance
from webapp.users.models import User
from webapp.libs.controlserver import check_version, get_images, get_flavors

app.config.from_object('config.DebugConfiguration') # configuration
manager = Manager(app, default_help_actions=False)

def sync(app):
	def action():
		# check version of virtual appliacne
		version = check_version()
		if not version:
			return action
		
		# update list of current images in db
		images = get_images()
		if not images:
			return action

		for image in images['images']:
			for attr, value in image:
				print attr, value

		# update the database with the images

		# update list of current flavors in db
		flavors = get_flavors()
		if not flavors:
			return action

		# update the database with the flavors

	return action


def resetdb(app):
	def action():
		os.system('./resetdb.sh')
		print "Database reset."
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
manager.add_action('resetdb', resetdb)
manager.add_action('serve', serve)

if __name__ == "__main__":
    manager.run()
