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

from webapp.models.models import User, Appliance, OpenStack, Status
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
	flavors = db.session.query(Flavors).filter(
		Flavors.locality != 2).filter(Flavors.locality != 0).all()

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

@mod.route('/configure/pool_flavors', methods=['GET'])
def pool_flavors_get():
	# fetch all flavors that came from the pool, the installed and non-installed ones
	flavors = db.session.query(Flavors).filter(Flavors.locality!=1).all()

	return render_template(
		'/configure/pool_flavors.html',
		settings=Status().check_settings(),
		flavors=flavors)

@mod.route('/configure/pool_flavors/<int:flavor_id>/<string:action>', methods=['PUT'])
def pool_flavors_put(flavor_id, action):
	try:
		flavor = Flavors.get_by_id(flavor_id)
		if not flavor:
			raise Exception("Flavor with id \"{0}\" not found.".format(flavor_id))
		if action == "install":
			response = flavor_verify_install(flavor)
			if not response['response'] == 'success':
				raise Exception(response['result']['message'])
			flavor.update(
				locality=3,
				active=True)
		elif action == "uninstall":
			response = flavor_uninstall(flavor)
			if not response['response'] == 'success':
				raise Exception(response['result']['message'])
			flavor.update(
				locality=2,
				active=False)
		else:
			raise Exception("Bad action \"{0}\".".format(action))
		instances = Instances()
		instances.toggle(flavor.id, flavor.active)
	except Exception as e:
		response = jsonify({"response": "error", "result": {"message": str(e)}})
		response.status_code = 500
		return response
	return jsonify({"response": "success"})

@mod.route('/configure/flavors/<int:flavor_id>', methods=['GET', 'PUT'])
@login_required
def configure_flavors_detail(flavor_id):
	# get the matching flavor
	flavor = db.session.query(Flavors).filter_by(id=flavor_id).first()

	# handle a GET
	if request.method == 'GET':
		# check configuration
		settings = Status().check_settings()

		# how much is a micro BTC?
		try:
			quote = float(coinbase_get_quote(currency='btc_to_usd')['result']['btc_to_usd'])/1000000
		except:
			quote = 0

		return render_template(
			'/configure/flavor_detail.html',
			settings=settings,
			quote=quote,
			flavor=flavor
		)

	# handle a PUT
	elif request.method == 'PUT':
		# clear settings cache
		Status().flush()

		try:
			state = int(request.form['enable'])
			flavor.active = state

			# set instances with this flavor to the state
			instances = Instances()
			instances.toggle(flavor.id, state)

		except:
			pass

		try:
			ask = request.form['ask']
			flavor.ask = ask
		except:
			pass

		os_ask = 0
		try:
			# get current ask price on openstack
			os_ask = flavor.ask_on_openstack
			# update entry
			flavor.update()
		# forbidden due to permissions or policy
		except nova_exceptions.Forbidden:
			# warn because we couldn't update the ask price that's set on openstack
			if os_ask != None:
				response = jsonify({"response": "error", "result": {
					"message": "Forbidden to update the asking price on OpenStack due"
						"to lack of permissions, refusing to update."}})
				response.status_code = 500
				return response
			# if open stack has no flavor price, only warn but don't error
			response = jsonify({"response": "warning", "result": {
				"message": "Forbidden to update the asking price on OpenStack due"
					"to lack of permissions, only updating local db."}})
			# do it again, but don't try to update openstack this time
			flavor.save(ignore_hooks=True)
			return response
			# if there is no ask price set on os we don't need to warn if we can't update it
		except nova_exceptions.ClientException as e:
			response = jsonify({"response": "error", "result": {
				"message": "Error in communication with OpenStack cluster."}})
			response.status_code = 500
			return response
		except:
			# warn because we couldn't talk to openstack
			response = jsonify({"response": "error", "result": {
				"message": "The ask rate is inavlid."}})
			response.status_code = 500
			return response

		return jsonify({"response": "success", "flavor": row2dict(flavor)})


# configure images page and dynamic images handler
@mod.route('/configure/images', methods=['GET', 'PUT'])
@login_required
def configure_images():
	# handle a GET
	if request.method == 'GET':
		# check configuration
		settings = Status().check_settings()

		# load images and appliance
		images = db.session.query(Images).all()
		appliance = Appliance().get()

		return render_template(
			'configure/images.html',
			settings=settings,
			appliance=appliance,
			images=images
		)

	# handle a PUT
	elif request.method == 'PUT':
		# clear settings cache
		Status().flush()
		
		# load appliance object
		appliance = Appliance().get()

		try:
			state = request.form['dynamicimages']
			appliance.dynamicimages = state
			
			# update entry
			appliance.update()
			
			if state == 0:
				state_out = "disabled"
			else:
				state_out = "enabled"

			response = {"response": "success", "result": "dynamicimages %s" % state_out}
		except:
			response = {"response": "error", "result": "no valid parameters supplied"}

		return jsonify(response)


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
			openstack.osusername = "%s" % dequote(keyvals['OS_USERNAME']) 
			openstack.ospassword = "changeme"

			# update entry
			openstack.update(openstack)

		elif file:
			# file type not allowed
			flash("File type not allowed or empty.  Try again.", "file-error")
		
		else:
			# user is manually updating form
			if form.validate_on_submit():
				# populate with form and update
				form.populate_obj(openstack)
				openstack.update(openstack)
				flash("OpenStack settings updated!", "success")

				return redirect(url_for(".configure_openstack"))
			else:
				flash("There were form errors. Please check your entries and try again.", "error")

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

	# images
	images = Images()
	images = images.get_all()

	return render_template(
		'configure/instances.html', 
		settings=settings, 
		instances=instances,
		images=images
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
