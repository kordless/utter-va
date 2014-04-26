#!/usr/bin/python
# manage.py
# -*- encoding:utf-8 -*-
import os
import sys

from flask import Flask
from flaskext.actions import Manager
from flask.ext.socketio import emit

from webapp import app, db, socketio

from webapp.models.models import Appliance, OpenStack, Images, Flavors, Instances, Addresses
from webapp.libs.utils import configure_blurb, query_yes_no, pprinttable
from webapp.libs.utils import coinbase_get_addresses, coinbase_check
from webapp.libs.utils import download_images
from webapp.libs.openstack import instance_start, image_install

# configuration file
if os.path.isfile('./DEV'): 
	app.config.from_object('config.DebugConfiguration')
else:
	app.config.from_object('config.BaseConfiguration')

# manager handler
manager = Manager(app, default_help_actions=False)

# USERLAND METHODS
# reset the entire system
default_ip = "0.0.0.0"
def reset(app):
	def action(ip=('i', default_ip)):
		try:
			if ip == default_ip:
				print "Please enter the appliance's IP address."
				print "Usage: ./manage.py reset -i x.x.x.x"
				return action

			# double check they want to do this	
			if query_yes_no("Are you sure you want to reset the appliance?"):

				# initialize database
				path = os.path.dirname(os.path.abspath(__file__))
				os.system('sqlite3 "%s/xoviova.db" < "%s/schema.sql"' % (path, path))

				# initialize the appliance object
				appliance = Appliance()
				appliance.initialize(ip)

				# sync with pool database
				images = Images()
				iresponse = images.sync(appliance)

				flavors = Flavors()
				fresponse = flavors.sync(appliance)

				if iresponse['response'] != "success":
					print iresponse['result']
				elif fresponse['response'] != "success":
					print iresponse['result']
				else:
					print "The database has been cleared and a new API token has been generated."
					configure_blurb()

		except ValueError as ex:
			print ex

	return action

# install
def install(app):
	def action(ip=('i', default_ip)):
		# run database reset script - use current path to run file
		path = os.path.dirname(os.path.abspath(__file__))

		# initialize database
		os.system('sqlite3 "%s/xoviova.db" < "%s/schema.sql"' % (path, path))
		
		# initialize the appliance object
		appliance = Appliance()
		appliance.initialize(ip)
		
		# sync to remote database
		images = Images()
		response = images.sync(appliance)

		flavors = Flavors()
		response = flavors.sync(appliance)

		# configure output
		configure_blurb()

	return action

# clean up all the extra tunnel.conf files (remove later)
def clean(app):
	def action():
		path = os.path.dirname(os.path.abspath(__file__))
		os.system('rm tunnel.conf.*')
	return action

# DEVELOPMENT METHODS
# serve application
def serve(app):
	def action():
		from werkzeug import SharedDataMiddleware

		# add static directory to be served by development server
		app.wsgi_app = SharedDataMiddleware(
			app.wsgi_app, 
			{'/': os.path.join(os.path.dirname(__file__), './webapp/static') }
		)
		# app.run(debug=True, host="0.0.0.0")
		socketio.run(app, host="0.0.0.0", port=5000)
		sys.exit()
	
	return action

# CRONTAB METHODS
# build the tunnel.conf file
def tunnel(app):
	def action():
		# get the appliance configuration
		appliance = db.session.query(Appliance).first()

		if appliance.ngroktoken:
			appliance.build_tunnel_conf()		
		else:
			configure_blurb()

	return action

# grab the pool server's flavors and install
def flavors(app):
	def action():
		# get the appliance for api token (not required, but sent if we have it)
		appliance = db.session.query(Appliance).first()

		# sync the flavors
		flavors = Flavors()
		response = flavors.sync(appliance)

		if "fail" in response['response']:
			print response['result']

	return action

# grab the pool server's images and download
def images(app):
	def action():
		# get the appliance for api token (not required, but sent if we have it)
		appliance = db.session.query(Appliance).first()

		# sync up all the images
		images = Images()
		response = images.sync(appliance)

		# now loop through and download if we don't have the files
		images = db.session.query(Images).all()
		download_images(appliance, images)

	return action

# grab the list of bitcoin addresses from coinbase
def addresses(app):
	def action():
		# get the appliance for coinbase tokens
		appliance = db.session.query(Appliance).first()

		# sync up all the addresses
		if coinbase_check(appliance):
			addresses = Addresses()
			response = addresses.sync(appliance)

	return action

# attach addresses to instance flavor preambles
def instances(app):
	def action():
		# get the appliance settings
		appliance = db.session.query(Appliance).first()

		# sync the instances
		instances = Instances()
		response = instances.warmup(appliance)

	return action

# beacon
# reports all sorts of stuff, like images installed, flavors known, etc.
def beacon(app):
	def action():
		emit('response', {'data': 'connected'}, broadcast=True)
	return action


# for development
manager.add_action('serve', serve)

# commands for user managment
manager.add_action('reset', reset)
manager.add_action('install', install)
manager.add_action('clean', clean)

# intended to run from cron
manager.add_action('tunnel', tunnel)
manager.add_action('flavors', flavors)
manager.add_action('images', images)
manager.add_action('addresses', addresses)
manager.add_action('instances', instances)

# socket actions
manager.add_action('beacon', beacon)

if __name__ == "__main__":
	manager.run()
