import re
import os
from urllib2 import urlopen

from flask import Blueprint, render_template, flash, redirect, session, url_for, request
from flask.ext.login import login_user, logout_user, current_user, login_required

from webapp import app, db, bcrypt, login_manager
from webapp.users.models import User
from webapp.api.models import Images, Flavors, Instances
from webapp.configure.models import OpenStack, Appliance
from webapp.configure.forms import OpenStackForm, ApplianceForm, InstanceForm
from webapp.libs.geoip import get_geodata
from webapp.libs.utils import generate_token, server_connect, coinbase_generate_address, coinbase_get_quote

mod = Blueprint('configure', __name__)

# check settings for setup warning indicators
def check_settings():
	# objects
	appliance = Appliance()
	openstack = OpenStack()
	images = Images()
	flavors = Flavors()

	# openstack connected?
	check_openstack = openstack.check()
	
	# appliance setup?
	check_appliance = appliance.check()
	
	# one image and one flavor installed?
	if images.check() and flavors.check():
		check_systems = True
	else:
		check_systems = False

	settings = {
		"appliance": check_appliance, 
		"systems": check_systems, 
		"openstack": check_openstack
	}
	
	return settings

# user login callback
@login_manager.user_loader
def load_user(user_id):
	return User.query.get(int(user_id))

# file upload extensions
ALLOWED_EXTENSIONS = set(['sh'])
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

# configure flavors and images page
@mod.route('/configure/systems', methods=['GET', 'POST'])
@login_required
def configure_systems():
	# check configuration
	settings = check_settings()

	# NOTE: POST handling is done via the API methods

	# load flavors and images
	flavors = db.session.query(Flavors).all()
	images = db.session.query(Images).all()
	
	return render_template('configure/systems.html', settings=settings, flavors=flavors, images=images)

# configuration pages
@mod.route('/configure', methods=['GET', 'POST'])
@login_required
def configure():
	# get the form for the page
	form = ApplianceForm(request.form)
	
	# page is POST'ing data
	if request.method == 'POST':
		# try to select one and only record
		appliance = db.session.query(Appliance).first()
		
		# load the form into the appliance object (excluding API token)
		apitoken = appliance.apitoken
		form.populate_obj(appliance)
		appliance.apitoken = apitoken
		
		if form.validate_on_submit():
			# our form validates, so update the database
			appliance.update(appliance)

			# build ngrok config file
			appliance.build_tunnel_conf()

			return redirect(url_for(".configure"))

		else:
			# form was not valid, so show errors	
			response = "There were form errors. Please check your entries and try again."
			flash(response, "error")
	
	# page is GET'ing data
	else:
		# get existing database entries
		appliance = db.session.query(Appliance).first()

		# populate the new form with seed location
		try:
			lat = float(appliance.latitude)
			lon = float(appliance.longitude)
		except ValueError, TypeError:
			try:
				geodata = get_geodata()
				appliance.latitude = geodata['latitude']
				appliance.longitude = geodata['longitude']
			except:
				appliance.latitude = 0
				appliance.longitude = 0		
	
	# check configuration
	settings = check_settings()

	# register token button
	validate_token = server_connect('validate', appliance.apitoken)

	if validate_token['result'] == "valid":
		register_button = {"icon": "check", "class": "success", "text": "Registered"} 
	else:
		register_button = {"icon": "flash", "class": "warning", "text": "Register API Token"} 
	
	return render_template('configure/appliance.html', settings=settings, form=form, appliance=appliance, button=register_button)

@mod.route('/configure/openstack', methods=['GET', 'POST'])
@login_required
def configure_openstack():
# quote strip
	def dequote(string):
		if string.startswith('"') and string.endswith('"'):
			string = string[1:-1]
		return string

	# check configuration
	settings = check_settings()

	# get the form
	form = OpenStackForm(request.form)

	# try to select one and only record
	openstack = db.session.query(OpenStack).first()

	# create new entry if configuration doesn't exist
	if not openstack:
		openstack = OpenStack()

	if request.method == 'POST':
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

	return render_template('configure/openstack.html', settings=settings, form=form, openstack=openstack)	


# configure instances page
@mod.route('/configure/instances', methods=['GET', 'POST'])
@login_required
def configure_instances():
	form = InstanceForm(request.form)

	# check configuration
	settings = check_settings()

	flavors = db.session.query(Flavors.osid, Flavors.name, Flavors.active).filter(Flavors.active.in_([1,2])).all()
	images = db.session.query(Images.osid, Images.name, Images.active).filter(Images.active.in_([1,2])).all()
	appliance = db.session.query(Appliance).first()

	if request.method == 'POST':
		if form.validate_on_submit():
			instance = Instances()

			# create a token and url for the callback
			instance_token = generate_token(size=16, caselimit=True)
			callback_url = "https://%s.%s/api/instances/%s/payment" % (appliance.subdomain, app.config['POOL_SSL_PROXY_DOMAIN'], instance_token)

			# give coinbase a holler
			appliance = db.session.query(Appliance).first()
			
			# call the coinbase method to create address
			response = coinbase_generate_address(appliance=appliance, callback_url=callback_url, label=instance_token)
			print response
			
			# test the response for validity
			if response['response'] == "success":
				# load form variables first
				form.populate_obj(instance)

				# update fields for loading into db
				instance.created = 0
				instance.updated = 0
				instance.expires = 0
				instance.publicipv4 = ""
				instance.publicipv6 = ""
				instance.ssltunnel = ""
				instance.osinstanceid = ""
				# 'name' is populated by form
				instance.state = 1 # indicate we have a payment address ready
				instance.token = instance_token
				instance.callbackurl = callback_url
				instance.paymentaddress = response['result']['address']

				# write to db
				instance.update(instance)

			else:
				flash("An error has occured with aquiring a payment address from Coinbase.", error)

		else:
			flash("A form validation error has occured.")

	# get the current price of a satoshi in USD (divide by 1,000,000)
	currency = "btc_to_usd"
	price = float(coinbase_get_quote(appliance=appliance, currency=currency)['result'][currency])/1000000
	print price

	# load instances
	instances = Instances()
	instances = instances.get_all()

	if instances:
		show_instances = True
	else:
		print "no instances"
		instances = []
		show_instances = False

	return render_template(
		'configure/instances.html', 
		settings=settings, 
		form=form, 
		instances=instances, 
		flavors=flavors, 
		images=images, 
		show_instances=show_instances, 
		price=price
	)


