#!/usr/bin/python
# manage.py
# -*- encoding:utf-8 -*-
import os
import sys
import json
import yaml
import urllib2

from collections import namedtuple
from subprocess import Popen
from urllib2 import urlopen
from flask import Flask
from flaskext.actions import Manager

from webapp import app, db

from webapp.models.models import Appliance, OpenStack, Images, Flavors, Instances
from webapp.libs.utils import configure_blurb, query_yes_no, pprinttable
from webapp.libs.utils import coinbase_get_addresses
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

				# initialize database (removes old tables)
				os.system('sqlite3 xoviova.db < schema.sql')

				# initialize the appliance object
				appliance = Appliance()
				appliance.initialize(ip)

				# sync with pool database
				images = Images()
				iresponse = images.sync()

				flavors = Flavors()
				fresponse = flavors.sync()

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
	def action(ip=('i', '0.0.0.0')):
		# run database reset script - use current path to run file
		path = os.path.dirname(os.path.abspath(__file__))

		# initialize database
		os.system('sqlite3 xoviova.db < schema.sql')
		
		# initialize the appliance object
		appliance = Appliance()
		appliance.initialize(ip)
		
		# sync to remote database
		images = Images()
		response = images.sync()

		flavors = Flavors()
		response = flavors.sync()

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
		app.run(debug=True, host="0.0.0.0")
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
		flavors = Flavors()
		response = flavors.sync()

	return action

# grab the pool server's images and download
def images(app):
	def action():
		# sync up all the images
		images = Images()
		response = images.sync()

		# now loop through and download if we don't have the files
		images = db.session.query(Images).all()

		# image path for this appliance
		image_path = "%s/webapp/static/images" % os.path.dirname(os.path.abspath(__file__))
		
		# finally, download what we've grabbed
		for image in images:
			filename = image.url.split('/')[-1]
			u = urllib2.urlopen(image.url)
			f = open("%s/%s" % (image_path, filename), 'wb')
			meta = u.info()
			size = int(meta.getheaders("Content-Length")[0])

			dlsize = 0
			while True:
				buffer = u.read(8192)
				if not buffer:
					break

				dlsize += len(buffer)
				f.write(buffer)
			f.close

	return action

# grab the list of bitcoin addresses from coinbase
def coinbase_sync(app):
	def action():
		appliance = db.session.query(Appliance).first()
		stuff = coinbase_get_addresses(appliance)
		for thing in stuff['result']['addresses']:
			print thing['address']['callback_url'], thing['address']['label']
	return action

# beacon
# reports all sorts of stuff, like images installed, flavors known, etc.
def beacon(app):
	def action():
		pass
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
manager.add_action('coinbase', coinbase_sync)

if __name__ == "__main__":
	manager.run()
