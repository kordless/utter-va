#!/usr/bin/python
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
from webapp.libs.twitterbot import get_stream, tweet_status

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

# show ips of running instances
def ips(app):
	def action():
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
# unlikely to occur during regular operations
def addressmop(app):
	def action():

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
			print response['result']['message']
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

		# check appliance is ready to go - exit if not
		settings = Status().check_settings()
		if not settings['ngrok'] or not settings['openstack']:
			log = "Running trashman - appliance is not ready."
			app.logger.error(log)
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
		# check appliance is ready to go - exit if not
		settings = Status().check_settings()
		if not settings['ngrok'] or not settings['openstack']:
			log = "Running salesman - appliance is not ready."
			app.logger.error(log)
			return action

		# get the appliance
		appliance = db.session.query(Appliance).first()

		# instances for sale, get 'em while they're hot
		instances = db.session.query(Instances).filter_by(state=1).all()

		# call the pool with instances for sale
		response = pool_salesman(instances, appliance)

	return action

# mix, pause, unpause instances
# runs every 5 minutes via cron
def housekeeper(app):
	def action():
		# check appliance is ready to go - exit if not
		settings = Status().check_settings()
		if not settings['ngrok'] or not settings['openstack']:
			log = "Running housekeeper - appliance is not ready."
			app.logger.error(log)
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
			Instances.state == 5
		)).all()

		# loop through them and do housekeeping
		for instance in instances:
			response = instance.housekeeping()

			# if instance isn't running
			if response['response'] == "fail":
				message(response['result']['message'], "error", True)
			else:
				if response['result']['message'] != "":
					message(response['result']['message'], "success", True)

	return action

# warmup and start instances
# runs every minute via cron
def instances(app):
	def action():
		# check appliance is ready to go - exit if not
		settings = Status().check_settings()
		if not settings['ngrok'] or not settings['openstack']:
			log = "Running instances - appliance is not ready."
			app.logger.error(log)
			return action

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
			if response['response'] == "fail":
				message(response['result']['message'], "error", True)
			else:
				if response['result']['message'] != "":
					message(response['result']['message'], "success", True)

	return action

# THIS IS A HUGE MESS
# handle the request queue from the twitter stream process
def falconer(app):
	def action():
		# get bot settings
		bot = TwitterBot.get()
		
		# exit if we're not enabled
		if not bot:
			return action
		if not bot.enabled:
			return action

		# get unhandled commands
		commands = db.session.query(TweetCommands).filter_by(state=1).all()

		for command in commands:
			if command.command == "instance":
				# check the user doesn't have another instance already
				ic = db.session.query(TweetCommands).filter_by(command="instance", user=command.user).count()
				if ic > 1 and command.user != "kordless":
					tweet_status("Sorry, I only do one instance per user.", command.user)
					command.delete(command)
					continue

				# grab an instance to reserve
				instance = Instances()
				response = instance.reserve(command.url, bot.flavor_id)
				message(response['result']['message'], response['response'], True)

				if response['response'] == "error":
					# tweet_status("Sorry, having system difficulties.  Please wait until human assisted notice.")
					print response['result']['message']
					continue		

				# update the command to reflect the new instance status
				instance = response['result']['instance']
				command.state = 10
				command.updated = int(time.time())
				command.instance_id = instance['id']
				command.update()
				
				# tweet bits
				ask = "%0.6f" % (float(response['result']['ask'])/1000000)
				address = response['result']['address']
				name = instance['name']
				
				# tell the user the bitcoin address
				tweet = "send %s BTC/hour to https://blockchain.info/address/%s in next 5 mins to start ~%s." % (ask, address, name)
				tweet_status(tweet, command.user)

			elif command.command.lower() == "status":
				
				# if instance is set, we use it
				if command.instance:
					if command.state == 10:
						# haven't paid for it, silly gooses
						tweet = "send %s BTC/hour to https://blockchain.info/address/%s to start ~%s." % (ask, address, name)
						tweet_status(tweet, command.user)					
					else:
						# get the time left in seconds
						epoch_time = int(time.time())
						expires = command.instance.expires
						timer = expires - epoch_time
						if timer < 0:
							timer = 0

						tweet_status("~%s | ipv6: %s | ipv4: %s | ipv4: %s | exp: %ss" % (
								command.instance.name,
								command.instance.publicipv6,
								command.instance.privateipv4,
								command.instance.publicipv4,
								timer
							),
							command.user
						)
				else:
					# no instance, so look up if they have an instance
					user_command = db.session.query(TweetCommands).filter_by(user=command.user, command="instance").first()
					command_count = db.session.query(TweetCommands).filter_by(command="instance").count()
					if user_command:
						tweet = "do a '@obitcoin !status ~%s'" % user_command.instance.name
						tweet_status(tweet, command.user)
					else:
						available = int(bot.max_instance) - int(command_count)
						tweet_status("%s of %s slots available to serve %s instances." % (
								available,
								bot.max_instances,
								bot.flavor.name
							), 
							command.user
						)
					pass

				command.delete(command)

		# update status of commands carrying an instance_id and update
		commands = db.session.query(TweetCommands).filter_by().all()

		for command in commands:
			if command.instance_id > 0:
				instance = db.session.query(Instances).filter_by(id=command.instance_id).first()

				# check if instance changed state
				if instance.state != command.state:
					# check if instance is in run state so we can tweet about it
					if instance.state == 4:
						print "tweeting"
						tweet_status("~%s | ipv6: %s | ipv4: %s | ipv4: %s" %
							(
								instance.name,
								instance.publicipv6,
								instance.privateipv4,
								instance.publicipv4
							),
							command.user
						)
					elif instance.state == 7:
						# decomissioned
						command.delete(command)
				
				# now sync the states
				command.state = instance.state
				command.update()

		# get reserved instance commands
		commands = db.session.query(TweetCommands).filter_by(state=10).all()

		for command in commands:
			if command.command == "instance":
				# check if timeout
				epoch_time = int(time.time())

				# cancel reservation if older than 7 minutes (we fudge this in the tweet)
				if (command.updated + 420) < epoch_time:
					instance = db.session.query(Instances).filter_by(id=command.instance_id).first()
					instance.callback_url = ""
					instance.state = 1
					instance.update()

					command.delete(command)
					message("Canceled reservation on %s." % instance.name, "warning", True)

	return action

# twitter stream + db storage
# uses a forever BLOCKING call to get_stream()
# runs from monit
def tweetstream(app):
	def action():
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

# advertising agent
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

# run from cron every 5 mintues
manager.add_action('housekeeper', housekeeper)

# run from cron every 1 minute
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

	# run the manager
	manager.run()
