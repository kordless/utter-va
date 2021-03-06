# -*- coding: utf-8 -*-
import re
import os
import time

from urllib2 import urlopen

from flask import Blueprint, render_template, jsonify, flash, redirect, session, url_for, request, make_response
from flask.ext.login import login_user, logout_user, current_user, login_required
from sqlalchemy import or_

from novaclient import exceptions as nova_exceptions

from webapp import app, db, bcrypt, login_manager

from webapp.models.models import User, Appliance, Status
from webapp.models.models import OpenStack
from webapp.models.images import Images
from webapp.models.flavors import Flavors
from webapp.models.instances import Instances 
from webapp.models.addresses import Addresses
from webapp.models.twitter import TwitterBot

from webapp.forms.forms import OpenStackForm, ApplianceForm, TwitterForm, BotForm

from webapp.libs.geoip import get_geodata
from webapp.libs.utils import row2dict, generate_token, message
from webapp.libs.coinbase import coinbase_generate_address, coinbase_get_quote
from webapp.libs.twitterbot import oauth_initialize, oauth_complete, tweet_status
from webapp.libs.openstack import flavor_verify_install, flavor_uninstall

mod = Blueprint('configure', __name__)

# user login callback
@login_manager.user_loader
def load_user(user_id):
	return User.query.get(int(user_id))

# file upload extensions
ALLOWED_EXTENSIONS = set(['sh'])
def allowed_file(filename):
		return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

# a second to minute filter for jinja2
@app.template_filter('sec2min')
def sec2min(value):
	return divmod(int(value), 60)[0]

# configure flavors page
@mod.route('/configure/flavors', methods=['GET'])
@login_required
def configure_flavors():
	# check configuration
	settings = Status().check_settings()

	# flavors without the ones that were synced from pool are not installed on 
	# openstack cluster yet
	flavors = Flavors.query.filter_by(installed=True).all()

	# load appliance
	appliance = Appliance.get()

	# how much is BTC?
	try:
		quote = float(coinbase_get_quote(currency='btc_to_usd')['result']['btc_to_usd'])/1000000
	except:
		quote = 0

	return render_template(
		'configure/flavors.html',
		settings=settings,
		quote=quote,
		flavors=flavors,
		appliance=appliance
	)

@mod.route('/configure/flavors/add', methods=['GET'])
def configure_flavors_add():
	# fetch all flavors that came from the pool, the installed and non-installed ones
	flavors = Flavors.query.filter_by(installed=False).all()

	return render_template(
		'/configure/flavor_add.html',
		settings=Status().check_settings(),
		flavors=flavors)

@mod.route('/configure/flavors/<int:flavor_id>', methods=['PUT'])
@login_required
def configure_flavors_detail(flavor_id):
	# get the matching flavor
	flavor = db.session.query(Flavors).filter_by(id=flavor_id).first()

	# clear settings cache
	Status().flush()

	# enable/diskable
	if 'enable' in request.form.keys():
		flavor.update(active=int(request.form['enable']))

	# set ask
	if 'ask' in request.form.keys():
		flavor.update(ask=int(request.form['ask']))

	# set max-instances
	if 'max-instances' in request.form.keys():
		flavor.update(max_instances=int(request.form['max-instances']))

	# install pool flavor
	if 'install' in request.form.keys():
		# let's see what we can break, er install
		try:
			if not flavor:
				response = jsonify({"response": "error", "result": {"message": "Flavor %s not found." % flavor_id }})
				response.status_code = 404
				return response

			# we are told to install
			if int(request.form['install']):
				response = flavor_verify_install(flavor)
				if not response['response'] == 'success':
					raise Exception(response['result']['message'])
				
				if flavor.ask > 0:
					flavor.update(active=True)
				else:
					flavor.update(active=False)
			else:
				# we are told to uninstall (install=0)
				response = flavor_uninstall(flavor)
				if not response['response'] == 'success':
					raise Exception(response['result']['message'])

				flavor.update(installed=False, active=False, osid=None)

		except Exception as e:
			response = jsonify({"response": "error", "result": {"message": str(e)}})
			response.status_code = 403
			return response

	# set instance state to match flavor's state
	instances = Instances()
	instances.toggle(flavor.id, flavor.active)

	# update the ask prices on the openstack cluster using metadata
	try:
		# get current ask price on openstack and update
		flavor.save()

	# warn because we couldn't update the ask price that's set on openstack
	except nova_exceptions.Forbidden:
		app.logger.warning('No permissions to update price of flavor "{0}".'.format(
											 flavor.name))
		return response
	
	# handle any other exception while talking to openstack
	except Exception as e:
		app.logger.warning('Error updating price of flavor "{0}": {1}.'.format(
											 flavor.name, str(e)))

	return jsonify({"response": "success", "flavor": row2dict(flavor)})


# configuration pages
@mod.route('/configure', methods=['GET', 'POST'])
@login_required
def configure():
	# get the form for the page
	form = ApplianceForm(request.form)

	# get existing database entries
	appliance = db.session.query(Appliance).first()

	# page is POST'ing data
	if request.method == 'POST':
		# clear settings cache
		Status().flush()
	
		# load the form into the appliance object (excluding API token)
		apitoken = appliance.apitoken
		form.populate_obj(appliance)
		appliance.apitoken = apitoken
		
		if form.validate_on_submit():
			# our form validates, so update the database
			appliance.update(appliance)

			# check the settings
			settings = Status().check_settings()

			if settings['coinbase']:				
				# sync up addresses with coinbase
				addresses = Addresses()
				addresses.sync(appliance)

				# grab the first address we got from coinbase
				address = db.session.query(Addresses).first()
				
				if address and address.subdomain:
					# overload the appliance's existing subdomain with one from coinbase address
					appliance.subdomain = address.subdomain
					appliance.update()
				else:
					# there exists no address with a subdomain, so we generate a new one
					appliance.subdomain = generate_token(size=16, caselimit=True)
					appliance.update()

				# build the tunnel config file - ngrok will start after it's built
				appliance.build_tunnel_conf()

				# not ideal, but whatever
				os.system('monit restart ngrok')

			# form was valid, so say thanks	
			flash("Setting have been saved.", "success")

		else:
			# form was not valid, so show errors	
			flash("There were form errors. Please check your entries and try again.", "error")
		
	# populate map
	try:
		lat = float(appliance.latitude)
		lon = float(appliance.longitude)
	except ValueError, TypeError:
		geodata = get_geodata()
		appliance.latitude = geodata['latitude']
		appliance.longitude = geodata['longitude']
		appliance.update()

	# check configuration
	settings = Status().check_settings()

	if settings['token'] == False:
		flash("Please register the API token.", "error")
	
	if settings['coinbase'] == False:
		flash("Please enter valid Coinbase credentials.", "error")

	if settings['ngrok'] == 0:
		flash("Please enter a valid Ngrok token.", "error")
	elif settings['ngrok'] == -1:
		flash("The Ngrok tunnel is not running.", "error")
		
	# return the template
	return render_template(
		'configure/appliance.html', 
		settings=settings, 
		form=form, 
		appliance=appliance
	)

@mod.route('/configure/openstack', methods=['GET', 'POST'])
@login_required
def configure_openstack():
# quote strip
	def dequote(string):
		if string.startswith('"') and string.endswith('"'):
			string = string[1:-1]
		return string

	# check configuration
	settings = Status().check_settings()

	# get the form
	form = OpenStackForm(request.form)

	# try to select one and only record
	openstack = db.session.query(OpenStack).first()


	# create new entry if configuration doesn't exist
	if not openstack:
		openstack = OpenStack()

	if request.method == 'POST':
		# clear settings cache
		Status().flush()

		# handle a file upload		
		try:
			file = request.files['file']
		except:
			file = False

		if file and allowed_file(file.filename):
			keyvals = {}
			for line in file:
				keyval = dict(re.findall(r'(\S+)=(".*?"|\S+)', line))
				if len(keyval) > 0:
					keyvals.update(keyval)
			
			# set values from extracted lines above - needs SQL injection protection?
			openstack.authurl = "%s" % dequote(keyvals['OS_AUTH_URL'])
			openstack.tenantname = "%s" % dequote(keyvals['OS_TENANT_NAME'])
			openstack.tenantid = "%s" % dequote(keyvals['OS_TENANT_ID'])
			try:
				openstack.region = "%s" % dequote(keyvals['OS_REGION_NAME'])

				if openstack.region == None:
					openstack.region = ""
			except:
				# don't need it
				openstack.region = ""
				pass
			openstack.osusername = "%s" % dequote(keyvals['OS_USERNAME'])
			openstack.ospassword = "changeme"

			# update entry
			openstack.update(openstack)

		elif file:
			# file type not allowed
			flash("File type not allowed or empty.  Try again.", "file-error")
		
		else:
			# user is manually updating form
			current_password = openstack.ospassword

			if form.validate_on_submit():
				# populate with form and update
				form.populate_obj(openstack)

				# check if password was blank and use old one
				if openstack.ospassword == "":
					openstack.ospassword = current_password

				openstack.update(openstack)

				flash("OpenStack settings updated!", "success")

			else:
				flash("There were form errors. Please check your entries and try again.", "error")

			# having to do this to get the form to update on password update
			return redirect("/configure/openstack")

	# get existing form data
	openstack = db.session.query(OpenStack).first()

	# if notice, show message
	return render_template(
		'configure/openstack.html', 
		settings=settings, 
		form=form, 
		openstack=openstack
	)	

# configure addresses page
@mod.route('/configure/addresses', methods=['GET', 'PUT'])
@login_required
def configure_addresses():
	# check configuration
	settings = Status().check_settings()

	# pull out the addresses
	addresses = db.session.query(Addresses).order_by("address asc").all()

	# render template
	return render_template(
		'configure/addresses.html',
		settings=settings,
		addresses=addresses
	)

# configure instances page
@mod.route('/configure/instances', methods=['GET', 'PUT'])
@login_required
def configure_instances():
	# check configuration
	settings = Status().check_settings()

	# load instances ordering by state
	instances = db.session.query(Instances).order_by("state desc").all()

	return render_template(
		'configure/instances.html', 
		settings=settings, 
		instances=instances,
	)

# configure instances page
@mod.route('/configure/instances/<int:instance_id>', methods=['GET', 'PUT'])
@login_required
def configure_instance_detail(instance_id):
	# check configuration
	settings = Status().check_settings()

	# load instance
	instance = db.session.query(Instances).filter_by(id=instance_id).first()

	if instance:
		# page is PUT'ing data - coinop 0 mBTC
		if request.method == 'PUT':
			response = instance.coinop(0)
			return jsonify(response)
		else:
			# GET
			return render_template(
				'configure/instance_detail.html', 
				settings=settings, 
				instance=instance
			)
	else:
		return redirect("/configure/instances")

# configure twitter bot (tweet, disconnect, disable/enable)
@mod.route('/configure/twitter/bot', methods=['POST'])
@login_required
def configure_twitter_tweet():
	# build response
	response = {"response": "success", "result": {"message": "Message goes here."}}

	# what are we suppose to do? (TODO convert to JSON POST, that's what)
	action = request.form.getlist('action')[0]
	
	# bot settings
	bot = TwitterBot.get()

	# tweet that shit
	if action == "tweet":
		ask = "%0.6f" % (float(bot.flavor.ask)/1000000)
		response = tweet_status(
			u"Up to (%s) %s instances are now on sale for %s μBTC/hour via '@%s !status'." % (
				bot.max_instances,
				bot.flavor.name, 
				ask,
				bot.screen_name
			)
		)

	# disconnect twitter creds
	elif action == "disconnect":
		# this MUST say 'settings' for stream restart
		tweet_status("Appliance !settings dropping bot credentials.")
		bot.delete(bot)
		response['result']['message'] = "Twitter credentials have been removed."

	# enable/disable bot
	elif action == "enabled":
		# this MUST say 'settings' for stream restart
		tweet_status("Appliance !settings enabling instance bot.")
		bot.enabled = True
		bot.update()
		response['result']['message'] = "Twitter bot has been enabled."

	elif action == "disabled":
		# this MUST say 'settings' for stream restart
		tweet_status("Appliance !settings disabling bot temporarily.  I'll be back.")
		bot.enabled = False
		bot.update()
		response['result']['message'] = "Twitter bot has been disabled."

	return jsonify(response)

# configure twitter bot auth
@mod.route('/configure/twitter', methods=['GET', 'POST'])
@login_required
def configure_twitter():
	# check configuration
	settings = Status().check_settings()

	# get the forms for the page
	form = TwitterForm(request.form)
	mrof = BotForm(request.form)

	# blow the flavors into a list
	flavor_list = []
	flavors = Flavors.get_all()
	for flavor in flavors:
		flavor_list.append((flavor.id, flavor.description))
	
	mrof.flavor.choices = flavor_list

	# twitter bot credentials
	bot = TwitterBot.get()

	# initialize the bot if it's not
	if not bot:
		bot = oauth_initialize()
	else:
		if bot.complete == 0:
			bot = oauth_initialize()

		if bot.complete == 1 and request.method == 'GET':
			# ensure we don't use stale creds
			bot = oauth_initialize()

		elif bot.complete == 1 and request.method == 'POST':
			if form.validate_on_submit():
				pin = request.form['pin']
				bot = oauth_complete(pin)
				if bot:
					flash("Authentication with Twitter complete.", "success")
				else:
					flash("Authentication with Twitter failed.", "error")
					bot = TwitterBot.get()
					bot.delete(bot)
					return redirect(url_for(".configure_twitter"))	
			else:
				# form was not valid, so show errors	
				flash("There were form errors. Please check your entries and try again.", "error")
				
		elif request.method == 'POST':
			if mrof.validate_on_submit():
				bot.flavor_id = mrof.flavor.data
				bot.announce = mrof.announce.data
				bot.max_instances = mrof.max_instances.data
				bot.updated = int(time.time())
				bot.update()

				if bot.announce > 0:
					# announce (requires 'settings' in comment to reload stream bot)
					tweet_status("Appliance settings updated. Now serving up to (%s) %s instances via '@%s !status'" % (
							bot.max_instances,
							bot.flavor.name,
							bot.screen_name
						)
					)
				flash("Bot settings updated.", "success")
			else:
				# form was not valid, so show errors	
				flash("There were form errors. Please check your entries and try again.", "error")	

	# no bot not hot
	if not bot:
		flash("Twitterbot failed to contact Twitter or get credentials.", "error")
		bot = None

	else:
		# set default form values
		mrof.flavor.data = bot.flavor_id
		mrof.announce.data = bot.announce

	return render_template(
		'configure/twitter.html',
		bot=bot,
		settings=settings,
		form=form,
		mrof=mrof
	)
