#!/usr/bin/env python
# -*- encoding:utf-8 -*-
# manage.py

import os
import sys
import time
import re
import gevent.monkey; gevent.monkey.patch_thread()

from IPy import IP
from flask import Flask
from flaskext.actions import Manager
from sqlalchemy import or_

from webapp import app, socketio, db

from webapp.models.models import User, Appliance, OpenStack, Status
from webapp.models.twitter import TwitterBot, TweetCommands
from webapp.models.images import Images 
from webapp.models.flavors import Flavors
from webapp.models.instances import Instances 
from webapp.models.addresses import Addresses

from webapp.libs.utils import query_yes_no, pprinttable, message
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

# user, what to do?
def configure_blurb():
	# get the appliance configuration
	appliance = db.session.query(Appliance).first()
	print "Visit http://%s/ to setup your appliance." % appliance.local_ip

# USERLAND METHODS
# reset the entire system
default_ip = "0.0.0.0"
def reset(app):
	def action(ip=('i', default_ip)):
		"""
		Restores the appliance to factory default settings.
		"""
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

# reset the admin account
def admin(app):
	def action(force=('f', 'false')):
		"""
		Resets the admin credentials.  Run this, then access 
		the appliance's web page to create a new admin account.
		"""
		if force == 'true':
			try:
				user = db.session.query(User).first()
				user.delete(user)
				print "The admin user has been deleted.  Please access the UI as soon as possible to create a new user."
				configure_blurb()
			except:
				print "Appliance currently has no users."
				configure_blurb()
		else:
			print "Doing nothing."
	return action

# install
def install(app):
	def action(ip=('i', default_ip)):
		"""
		Installs a new database configuration for the appliance.
		"""
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
# serve application for development (in production we start it from monit)
def serve(app):
	def action(gunicorn=('g', 'false')):
		"""
		Starts the development server.
		"""
		if gunicorn == 'true':
			path = os.path.dirname(os.path.abspath(__file__))
			# start gunicorn for development
			os.system('gunicorn --max-requests 1 --access-logfile ./logs/access-log --error-logfile ./logs/error-log -c gunicorn.conf.py webapp:app')
			sys.exit()
		else:
			socketio.run(app, host=default_ip)

	return action

# coinop command
def coinop(app):
	def action(
		amount=('a', 0),
		instance=('i', "smi-a4t0zcoe")
	):
		"""
		Makes fake Bitcoin payments to the appliance.  Example usage 
		paying instance 'ami-a4t0zcoe' 20 micro Bitcoin: 

		./manage.py coinop -a 20 -i ami-a4t0zcoe
		
		"""
		instance = db.session.query(Instances).filter_by(name=iname).first()
		if amount == 0:
			print "Enter a whole amount to pay instance."
		elif instance:
			print "Paying %s mBTC to instance %s." % (amount, iname)
			instance.coinop(amount)
		else:
			print "Can't find that instance!"
	return action

# show ips of running instances
def ips(app):
	def action():
		"""
		Prints a list of current instances and their IP addresses.
		"""
		from webapp.libs.openstack import instance_info

		# check appliance is ready to go - exit if not
		settings = Status().check_settings()
		if not settings['ngrok'] or not settings['openstack']:
			print "Appliance is not ready."
			return action

		instances = db.session.query(Instances).filter_by(state=4).all()

		if not instances:
			print "No instances are running.\n"

		for instance in instances:
			print "Instance %s" % instance.name
			print "====================="

			# get instance (server) info
			response = instance_info(instance)
			server = response['result']['server']

			for key in server.networks.keys():
				for network in server.networks[key]:
					print "%s IPv%s: %s" % (IP(network).iptype(), IP(network).version(), network)
			
			# line break
			print

	return action

# cleans up errant address assignments
def addressmop(app):
	def action():
		"""
		Clean up errant address to instance assignments.
		"""
		# check appliance is ready to go - exit if not
		settings = Status().check_settings()
		if not settings['ngrok'] or not settings['openstack']:
			print "Appliance is not ready."
			return action

		instances = db.session.query(Instances).all()
		addresses = db.session.query(Addresses).all()

		# build an array of address ids from current instances
		addresses_used = []
		for instance in instances:
			addresses_used.append(instance.address.id)

		# build an array of address ids
		addresses_known = []
		for address in addresses:
			addresses_known.append(address.id)
		
		# build the remove list
		addresses_remove = [address for address in addresses_known if address not in addresses_used]

		# zero out the ones to remove - if any
		for address in addresses:
			if address.id in addresses_remove:
				address.instance_id = 0

	return action

# quick and dirty openstack stats
def stats(app):
	def action():
		"""
		Prints current hypervisor usage information.
		"""
		from webapp.libs.openstack import get_stats

		# check appliance is ready to go - exit if not
		settings = Status().check_settings()
		if not settings['ngrok'] or not settings['openstack']:
			print "Appliance is not ready."
			return action

		stats = get_stats()

		print stats['result']['message']
		for key in stats['result']['stats']:
			print
			print key 
			print stats['result']['stats'][key]

	return action

# message client
def messenger(app):
	def action(
		text=('m', 'Hello from the administration console!'),
		status=('s', 'success'),
		reloader=('r', '0')
	):
		"""
		Send messages and reload request to a browser connected to the appliance.
		"""
		# muck the reload flags around
		if reloader == '1' or reloader.lower() == 'true':
			reloader = True
		else:
			reloader = False

		# send out the message
		message(text, status, reloader)
	return action

# build the tunnel.conf file
def tunnel(app):
	def action():
		"""
		Builds a new Ngrok tunnel configuration file.
		"""
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
		"""
		Verify authentication token is being accepted by pool.
		"""
		# get the appliance configuration
		appliance = db.session.query(Appliance).first()

		if appliance.apitoken:
			response = pool_connect("authorization", appliance)
			print response['result']['message']
		else:
			configure_blurb()

	return action

# CRONTAB METHODS
# grab the pool server's flavors and install
# runs every 15 minutes via cron
def flavors(app):
	def action():
		"""
		Performs a sync from the pool's list of flavors to the appliance.

		Cron: Every 15 minutes.
		"""
		# get the appliance for api token (not required, but sent if we have it)
		appliance = db.session.query(Appliance).first()

		# sync the flavors
		flavors = Flavors()

		flavors.sync(appliance)
		flavors.sync_from_openstack(appliance)

	return action

# grab the pool server's images and download
# runs every 15 minutes via cron
def images(app):
	def action():
		"""
		Performs a sync from the pool's list of images to the appliance.
		
		Cron: Every 15 minutes.
		"""
		# get the appliance for api token (not required, but sent if we have it)
		appliance = db.session.query(Appliance).first()

		# sync up all the images
		images = Images()
		response = images.sync(appliance)

		# now loop through and download non dynamic images if we don't have the files
		images = db.session.query(Images).filter_by(cache=1).all()
		download_images(appliance, images)

		# clear out old dynamic images
		images = db.session.query(Images).filter_by(cache=0).all()
		for image in images:
			image.housekeeping()		

	return action

# cleans up decomissioned and errant instances
# runs every 15 minutes via cron
def trashman(app):
	def action():
		"""
		Removes decomissioned and errant instances.  Also takes out the trash occasionally.

		Cron: Every 15 minutes.
		"""
		# check appliance is ready to go - exit if not
		settings = Status().check_settings()
		if not settings['ngrok'] or not settings['openstack']:
			app.logger.error("Running trashman - appliance is not ready.")
			return action

		instances = db.session.query(Instances).filter_by(state=7).all()

		for instance in instances:
			response = instance.trashman()
			message(response['result']['message'], "success", True)

	return action

# salesman puts up instances for sale on pool
# runs every 15 minutes via cron
def salesman(app):
	def action():
		"""
		Puts instances up for sale on the pool.

		Cron: Every 15 minutes.
		"""
		# check appliance is ready to go - exit if not
		settings = Status().check_settings()
		if not settings['ngrok'] or not settings['openstack']:
			app.logger.error("Running salesman - appliance is not ready.")
			return action

		# get the appliance
		appliance = db.session.query(Appliance).first()

		# instances for sale, get 'em while they're hot
		instances = db.session.query(Instances).filter_by(state=1).all()

		# call the pool with instances for sale
		response = pool_salesman(instances, appliance)

	return action

# mix, pause, unpause instances - remove old dynamic images
# runs every 5 minutes via cron
def housekeeper(app):
	def action():
		"""
		Provides housekeeping services including mix, pause and decomission.

		Cron: Every 5 minutes.
		"""
		# check appliance is ready to go - exit if not
		settings = Status().check_settings()
		if not settings['ngrok'] or not settings['openstack']:
			app.logger.error("Running housekeeper - appliance is not ready.")
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
			Instances.state == 2,
			Instances.state == 4,
			Instances.state == 5
		)).all()

		# loop through them and do housekeeping
		for instance in instances:
			response = instance.housekeeping()

			# if instance isn't running
			if response['response'] == "error":
				message(response['result']['message'], "error", True)
			else:
				if response['result']['message'] != "":
					message(response['result']['message'], "success", True)

	return action

# warmup and start instances
# runs every minute via cron
def instances(app):
	def task():
		# START
		# instances which have received payment are moved to starting
		instances = db.session.query(Instances).filter_by(state=2).all()
		for instance in instances:
			response = instance.start()

			if response['response'] == "success":
				message("Instance %s launched." % instance.name, "success", True)
			else:
				message("%s Unable to launch instance %s." % (
						response['result']['message'],
						instance.name
					), 
					"error", 
					True
				)
				instance.message = response['result']['message']
				instance.update()

		# NUDGE
		# instances in the process of starting are monitored and updated
		instances = db.session.query(Instances).filter_by(state=3).all()
		for instance in instances:
			response = instance.nudge()

			if response['response'] == "success":
				message("Instance %s is now running." % instance.name, "success", True)

		# RELIGHT
		# instances which have unpaused via payment
		instances = db.session.query(Instances).filter_by(state=6).all()
		
		# loop through them and do housekeeping
		for instance in instances:
			response = instance.housekeeping()

			# if instance isn't running
			if response['response'] == "error":
				message(response['result']['message'], "error", True)
				instance.message = response['result']['message']
				instance.update()
			else:
				if response['result']['message'] != "":
					message(response['result']['message'], "success", True)

		return

	def action(
			cron=('c', 0),
			freq=('f', 0),
		):
		"""
		Provides instance services including start, nudge and relight.

		Cron: Every 1 minute.
		"""
		# check appliance is ready to go - exit if not
		settings = Status().check_settings()
		if not settings['ngrok'] or not settings['openstack']:
			app.logger.error("Running instances - appliance is not ready.")
			return action

		# check flags for non-cron run (for dev)
		if cron == 0 or freq == 0:
			task()
			return action

		# current UTC time in seconds since epoch
		epoch_time = int(time.time())

		# cron, frequency length in seconds, run_time
		cron_frequency = cron
		frequency = freq
		run_time = 0

		# do a single run
		timer_in = int(time.time())
		task()
		timer_out = int(time.time())

		# run task X many more times per cron period
		for x in range(1,cron_frequency/frequency):
			# run time
			run_time = timer_out - timer_in

			# sleep for a a bit
			if run_time < frequency:
				time.sleep(frequency - run_time)

			# check if we are going to go over on next run
			est_time = (frequency * x) + run_time
			if est_time > cron_frequency:
				break

			# wrap task above with time in and out
			timer_in = int(time.time())
			task()
			timer_out = int(time.time())

	return action

# twitter stream + db storage
# uses a forever BLOCKING call to get_stream()
# runs from monit
def tweetstream(app):
	def action():
		"""
		Stream process for Twitter monitoring.  Do not run directly.
		"""
		from webapp.libs.twitterbot import get_stream

		# bot settings
		bot = TwitterBot.get()

		if bot:
			if bot.enabled:
				get_stream()
			else:
				# we're going to exit, and monit will try to restart
				# delay that a bit so monit doesn't freak out
				time.sleep(60)
		else:
			time.sleep(60)

	return action

# handle the request queue from the twitter stream process
def falconer(app):
	def task(bot):
		from webapp.libs.twitterbot import tweet_status, run_status, reserve_instance, check_instance, cleanup_reservations

		# get unhandled commands
		commands = db.session.query(TweetCommands).filter_by(state=1).all()

		for command in commands:
			# someone typed '!instance'
			if command.command == "instance":

				# reserve instance
				response = reserve_instance(command, bot)

				if response['response'] == "error":
					print response['result']['message']
					command.delete(command)

			# someone typed '!status'
			elif command.command.lower() == "status":

				# send status info
				response = run_status(command, bot)

				if response['response'] == "error":
					print response['result']

				# don't hold onto status commands
				command.delete(command)

			elif command.command.lower() == "help":
				response = tweet_status("'@%s !instance ^http://pastebin⋅com/raw.php?i=zX5fD6HY' & pay. Edit pastebin to suit! Also, '@%s !status'." % (bot.screen_name, bot.screen_name), command.user)

				if response['response'] == "error":
					print response['result']
				
				command.delete(command)

			else:
				# some other command or errant tweet
				command.delete(command)

		# update status of commands carrying an instance_id and update
		commands = db.session.query(TweetCommands).filter_by().all()
		for command in commands:
			# run an instance check
			check_instance(command, bot)

		# get pending reserved instance commands
		commands = db.session.query(TweetCommands).filter_by(state=10).all()

		for command in commands:
			cleanup_reservations(command, bot)

		return

	def action(
			cron=('c', 0),
			freq=('f', 0),
		):
		"""
		Provides Twitter command processing.

		Cron: Every 1 minute.
		"""

		# get bot settings
		bot = TwitterBot.get()
		
		# exit if we're not enabled
		if not bot:
			return action
		if not bot.enabled:
			print "The marketing bot is disabled."
			return action

		# check flags for non-cron run (for dev)
		if cron == 0 or freq == 0:
			task(bot)
			return action

		# current UTC time in seconds since epoch
		epoch_time = int(time.time())

		# cron, frequency length in seconds, run_time
		cron_frequency = cron
		frequency = freq
		run_time = 0

		# do a single run
		timer_in = int(time.time())
		task(bot)
		timer_out = int(time.time())

		# run task X many more times per cron period
		for x in range(1,cron_frequency/frequency):
			# run time
			run_time = timer_out - timer_in

			# sleep for a a bit
			if run_time < frequency:
				time.sleep(frequency - run_time)

			# check if we are going to go over on next run
			est_time = (frequency * x) + run_time
			if est_time > cron_frequency:
				break

			# wrap task above with time in and out
			timer_in = int(time.time())
			task(bot)
			timer_out = int(time.time())

	return action

# advertising agent
# announce instances
def marketeer(app):
	def action():
		"""
		Posts marketing blurbs to Twitter.

		Cron: Depends on offering period.
		"""
		import random
		from webapp.libs.twitterbot import tweet_status

		# get bot settings
		bot = TwitterBot.get()

		# get the time
		epoch = int(time.time())

		if not bot:
			print "The marketing bot is disabled."
			return action

		if bot.announce == 0:
			print "The marketing bot is disabled."
			return action

		# if updated + announce > current time, do an update!
		if epoch > (bot.updated + (bot.announce * 3600)):
			# make up some stuff
			blurbs = [
				"Get your hot-n-fresh #openstack instances! ",
				"Instances for nothing and #bitcoins for free. ",
				"Now serving #42. ",
				"Pssst. Hey buddy, want some #openstack? ",
				"Sorry #openstack, we're all out of IPv4 addresses. ",
				"Any significantly advanced technology is indistinguishable from magic. ",
				"It's #bitcoin magic! ",
				"I'm hungry. Spare some #bitcoin? "
			]
			hashtags = [
				"trust",
				"cryptocurrency",
				"transparency",
				"globalcloud",
				"federation",
				"virtualization",
				"monkeys"
			]
			blurb = random.choice(blurbs)
			hashtag = random.choice(hashtags)
			
			# say it
			tweet_status("%s '@%s !status' for more info. #%s" % (blurb, bot.screen_name, hashtag))
			
			# update
			bot.updated = int(time.time())
			bot.update()

	return action

# http://pastebin.com/raw.php?i=zX5fD6HY

# for development
manager.add_action('serve', serve)
manager.add_action('coinop', coinop)
manager.add_action('message', messenger)
manager.add_action('ips', ips)
manager.add_action('stats', stats)
manager.add_action('addressmop', addressmop)
manager.add_action('admin', admin)

# commands for user managment
manager.add_action('reset', reset)
manager.add_action('install', install)
manager.add_action('tunnel', tunnel)
manager.add_action('checkauth', checkauth)

# run from cron every 15 minutes
manager.add_action('images', images)
manager.add_action('flavors', flavors)
manager.add_action('trashman', trashman)
manager.add_action('salesman', salesman)
manager.add_action('marketeer', marketeer)

# run from cron every 5 mintues
manager.add_action('housekeeper', housekeeper)

# run from cron every minute
manager.add_action('instances', instances)
manager.add_action('falconer', falconer)

# twitter commands run from monit in prod
manager.add_action('tweetstream', tweetstream)

if __name__ == "__main__":

	# manager logs
	import logging
	from logging.handlers import RotatingFileHandler

	# delete existing handlers
	del app.logger.handlers[:]
	handler = RotatingFileHandler('%s/logs/utter.log' % os.path.dirname(os.path.realpath(__file__)), maxBytes=1000000, backupCount=7)
	handler.setLevel(logging.INFO)
	log_format = "%(asctime)s - %(levelname)s - %(message)s"
	formatter = logging.Formatter(log_format)
	handler.setFormatter(formatter)
	app.logger.addHandler(handler)

	# deal with glance client logs
	logging.getLogger('glanceclient.common.http').addHandler(handler)
	
	# run the manager
	manager.run()
