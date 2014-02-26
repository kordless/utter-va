#!/usr/bin/python
# manage.py
# -*- encoding:utf-8 -*-
import os
import sys
import json
import yaml

from collections import namedtuple
from subprocess import Popen
from urllib2 import urlopen
from flask import Flask
from flaskext.actions import Manager

from webapp import app, db
from webapp.configure.models import Appliance, OpenStack
from webapp.api.models import Images, Flavors, Instances
from webapp.libs.utils import configure_blurb, query_yes_no, pprinttable
from webapp.libs.openstack import instance_start

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
				iresponse = images.sync(appliance.apitoken)

				flavors = Flavors()
				fresponse = flavors.sync(appliance.apitoken)

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

def list(app):
	def action():
		instances = Instances().get_all()
		table = []
		Row = namedtuple('Row', ['id', 'name', 'token', 'payment_address', 'state'])
		for instance in instances:
			data = Row(instance.id, instance.name, instance.token, instance.paymentaddress, instance.state)
			table.append(data)

		# print table of instances
		pprinttable(table)

	return action

def start(app):
	def action(instance_token=('default')):
		if instance_token == 'default':
			print "Enter the token for the instance you want to start."
		else:
			instance = Instances().get_by_token(instance_token)
			if instance == None:
				print "Instance with token '%s' not found." % instance_token
			else:
				instance_start(instance)
				print "Started instance '%s'." % instance.name

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
manager.add_action('list', list)
manager.add_action('start', start)

if __name__ == "__main__":
	manager.run()
