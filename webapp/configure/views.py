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
from webapp.libs.utils import generate_token
from webapp.libs.blockchain import blockchain_address

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

			# create a token and secret, call blockchain to create callback address
			instance_token = generate_token(size=16, caselimit=True)
			instance_secret = generate_token(size=16, caselimit=False)
			callback_url = "https://%s.%s/api/instances/%s/payment" % (appliance.subdomain, app.config['POOL_SSL_PROXY_DOMAIN'], instance_token)
			
			# give blockchain.info a holler
			response = blockchain_address(appliance.paymentaddress, callback_url)

			# test the response for validity
			if response['response'] == "success":
				# load form variables first
				form.populate_obj(instance)

				# get dict object from blockchain
				result = response['result'] 

				# update fields for loading into db
				instance.created = 0
				instance.updated = 0
				instance.expires = 0
				instance.publicip = ""
				instance.ssltunel = ""
				instance.osinstanceid = ""
				# 'name' is poplulated by form
				instance.state = 1 # indicate we have a payment address ready
				instance.token = instance_token
				instance.secret = instance_secret
				instance.confirmations = 0
				instance.callbackurl = callback_url
				instance.feepercent = result['fee_percent']
				instance.destination = appliance.paymentaddress
				instance.inputaddress = result['input_address']
				instance.transactionhash = ""

				# write to db
				instance.update(instance)

			else:
				flash("An error has occured with aquiring a payment address from Blockchain.")

		else:
			flash("A form validation error has occured.")
	
	# load instances
	instances = db.session.query(Instances).all()
	if len(instances) > 0:
		show_instances = True
	else:
		show_instances = False

	return render_template('configure/instances.html', settings=settings, form=form, instances=instances, flavors=flavors, images=images, show_instances=show_instances)

# configuration pages
@mod.route('/configure', methods=['GET', 'POST'])
@login_required
def configure():
	# check configuration
	settings = check_settings()

	# get the form
	form = ApplianceForm(request.form)
	
	if request.method == 'POST':
		if form.validate_on_submit():
			# try to select one and only record
			appliance = db.session.query(Appliance).first()
			
			# create if no existing entry
			if not appliance:
				appliance = Appliance()
			
			# store ngrok info
			current_ngrok_token = appliance.ngroktoken
			new_ngrok_token = request.form['ngroktoken']

			# create new entry, populate with form, write to db
			form.populate_obj(appliance)
			appliance.apitoken = request.form['api-token-hidden']
			appliance.update(appliance)

			# build ngrok config file
			appliance.build_tunnel_conf()

			return redirect(url_for(".configure"))

		else:
			response = False
			for error in form.paymentaddress.errors:
				response = error
			if not response:
				response = "There were form errors. Please check your entries and try again."
			flash(response, "form-error")

	# get existing form data
	appliance = db.session.query(Appliance).first()

	# if no geodata, get it
	if not appliance:
		appliance = {}
		try:
			geodata = get_geodata()
			appliance['latitude'] = geodata['latitude']
			appliance['longitude'] = geodata['longitude']
		except:
			appliance['latitude'] = 0
			appliance['longitude'] = 0	
	else:
		# populate the new form with seed location
		try:
			# test the values are correct
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

	return render_template('configure/appliance.html', settings=settings, form=form, appliance=appliance)


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

				return redirect(url_for(".configure_openstack"))
			else:
				flash("There were form errors. Please check your entries and try again.", "form-error")

	# get existing form data
	openstack = db.session.query(OpenStack).first()

	return render_template('configure/openstack.html', settings=settings, form=form, openstack=openstack)	


