#!/usr/bin/python
# manage.py
# -*- encoding:utf-8 -*-
import os
import sys
import time
import gevent.monkey; gevent.monkey.patch_thread()

from flask import Flask
from flaskext.actions import Manager
from sqlalchemy import or_

from webapp import app, socketio, db

from webapp.models.models import Appliance, Status
from webapp.models.models import OpenStack, Images, Flavors
from webapp.models.models import Instances, Addresses

from webapp.libs.utils import configure_blurb, query_yes_no, pprinttable, message
from webapp.libs.coinbase import coinbase_get_addresses, coinbase_checker
from webapp.libs.images import download_images
from webapp.libs.pool import pool_salesman, pool_connect

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
				os.system('sqlite3 "%s/utterio.db" < "%s/schema.sql"' % (path, path))

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
		os.system('sqlite3 "%s/utterio.db" < "%s/schema.sql"' % (path, path))
		
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

# DEVELOPMENT METHODS
# serve application via dev server or gunicorn)
def serve(app):
	def action(dev=('d', 'false')):
		if dev == 'true':
			socketio.run(app, host=default_ip)
		else:
			path = os.path.dirname(os.path.abspath(__file__))
			os.system('gunicorn -c gunicorn.conf.py webapp:app')
			sys.exit()
	
	return action

# coinop command
def coinop(app):
	def action(
		amount=('a', 0),
		iname=('i', '')
	):
		instance = db.session.query(Instances).filter_by(name=iname).first()
		if amount == 0:
			print "Enter a whole amount to pay instance."
		elif instance:
			print "Paying %s mBTC to instance %s." % (amount, iname)
			instance.coinop(amount)
		else:
			print "Can't find that instance!"
	return action

# message client
def messenger(app):
	def action(
		text=('m', 'Hello from the administration console!'),
		status=('s', 'success'),
		reloader=('r', '0')
	):
		# muck the reload flags around
		if reloader == '1' or reloader == 'true':
			reloader = True
		else:
			reloader = False

		# send out the message
		message(text, status, reloader)
	return action

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

# check authorization
def checkauth(app):
	def action():
		# get the appliance configuration
		appliance = db.session.query(Appliance).first()

		if appliance.apitoken:
			response = pool_connect("authorization", appliance)		
			print response
		else:
			configure_blurb()

	return action


# CRONTAB METHODS
# grab the pool server's flavors and install
# runs every 15 minutes via cron
def flavors(app):
	def action():
		# get the appliance for api token (not required, but sent if we have it)
		appliance = db.session.query(Appliance).first()

		# sync the flavors
		flavors = Flavors()
		response = flavors.sync(appliance)

	return action

# grab the pool server's images and download
# runs every 15 minutes via cron
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
	
# warmup and start instances
# runs every minute via cron
def instances(app):
	def action():
		# check appliance is ready to go - exit if not
		settings = Status().check_settings()
		if not settings['ngrok'] or not settings['openstack']:
			print "Appliance is not ready."
			return action

		# START
		# instances which have received payment are moved to starting
		instances = db.session.query(Instances).filter_by(state=2).all()
		for instance in instances:
			response = instance.start()

			if response['response'] == "success":
				message("Instance %s launched." % instance.name, "success", True)
			else:
				message(response['result']['message'], "error", True)

		# NUDGE
		# instances in the process of starting are monitored and updated
		instances = db.session.query(Instances).filter_by(state=3).all()
		for instance in instances:
			response = instance.nudge()

			if response['response'] == "success":
				message("Instance %s is now running." % instance.name, "success", True)

	return action

# mix, pause, unpause instances
# runs every 5 minutes via cron
def housekeeper(app):
	def action():
		# check appliance is ready to go - exit if not
		settings = Status().check_settings()
		if not settings['ngrok'] or not settings['openstack']:
			print "Appliance is not ready."
			return action

		# MIXING
		# make sure we have mixed an instance for each flavor
		instances = Instances()
		flavors = db.session.query(Flavors).filter_by(active=1).all()
		for flavor in flavors:
			response = instances.mix(flavor)

			if response['response'] != "success":
				message("Instance mixing failed. Something is wrong.")

		# HOUSEKEEPING
		# general houskeeping work including pausing, unpausing
		# runs on all currently running and suspended instances
		instances = db.session.query(Instances).filter(or_(
			Instances.state == 4,
			Instances.state == 5,
			Instances.state == 6
		)).all()

		# loop through them and do housekeeping
		for instance in instances:
			response = instance.housekeeping()

			# if instance ins't running
			if response['response'] == "fail":
				message(response['result']['message'], "error", True)
			else:
				if response['result']['message'] != "":
					message(response['result']['message'], "success", True)

	return action

# cleans up decomissioned and errant instances
# runs every 10 minutes via cron
def trashman(app):
	def action():

		# check appliance is ready to go - exit if not
		settings = Status().check_settings()
		if not settings['ngrok'] or not settings['openstack']:
			print "Appliance is not ready."
			return action

		instances = db.session.query(Instances).filter_by(state=7).all()

		for instance in instances:
			response = instance.trashman()
			message(response['result']['message'], "success", True)

	return action

# salesman puts up instances for sale on pool
# runs every 5 minutes via cron
def salesman(app):
	def action():
		# check appliance is ready to go - exit if not
		settings = Status().check_settings()
		if not settings['ngrok'] or not settings['openstack']:
			print "Appliance is not ready."
			return action

		# get the appliance
		appliance = db.session.query(Appliance).first()

		# instances for sale, get 'em while they're hot
		instances = db.session.query(Instances).filter_by(state=1).all()

		# call the pool with instances for sale
		response = pool_salesman(instances, appliance)
		
	return action

# for development
manager.add_action('serve', serve)
manager.add_action('coinop', coinop)
manager.add_action('message', messenger)

# commands for user managment
manager.add_action('reset', reset)
manager.add_action('install', install)
manager.add_action('tunnel', tunnel)
manager.add_action('checkauth', checkauth)

# run from cron every 1 minute
manager.add_action('instances', instances)

# run from cron every 5 mintues
manager.add_action('housekeeper', housekeeper)

# run from cron every 15 minutes
manager.add_action('images', images)
manager.add_action('flavors', flavors)
manager.add_action('trashman', trashman)
manager.add_action('salesman', salesman)

if __name__ == "__main__":
	manager.run()
