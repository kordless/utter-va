import re
import os
from urllib2 import urlopen

from flask import Blueprint, render_template, jsonify, flash, redirect, session, url_for, request
from flask.ext.login import login_user, logout_user, current_user, login_required

from webapp import app, db, bcrypt, login_manager

from webapp.models.models import User, Appliance, Status
from webapp.models.models import Images, Flavors, OpenStack
from webapp.models.models import Instances, Addresses

from webapp.forms.forms import OpenStackForm, ApplianceForm, InstanceForm

from webapp.libs.geoip import get_geodata
from webapp.libs.utils import row2dict, generate_token
from webapp.libs.pool import pool_api_connect
from webapp.libs.coinbase import coinbase_generate_address, coinbase_get_quote

mod = Blueprint('configure', __name__)

# user login callback
@login_manager.user_loader
def load_user(user_id):
	return User.query.get(int(user_id))

# file upload extensions
ALLOWED_EXTENSIONS = set(['sh'])
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

# configure flavors page
@mod.route('/configure/flavors', methods=['GET'])
@login_required
def configure_flavors():
	# check configuration
	settings = Status().check_settings()

	# load flavors
	flavors = db.session.query(Flavors).all()

	# how much is BTC?
	try:
		quote = float(coinbase_get_quote(currency='btc_to_usd')['result']['btc_to_usd'])/100000
	except:
		quote = 0

	return render_template(
		'configure/flavors.html',
		settings=settings,
		quote=quote,
		flavors=flavors
	)

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

		# update entry
		flavor.update()

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
		print appliance.dynamicimages

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
			response = {"response": "fail", "result": "no valid parameters supplied"}

		return jsonify(response)


# configuration pages
@mod.route('/configure', methods=['GET', 'POST'])
@login_required
def configure():
	# get the form for the page
	form = ApplianceForm(request.form)

	# page is POST'ing data
	if request.method == 'POST':
		# clear settings cache
		Status().flush()

		# try to select one and only record
		appliance = db.session.query(Appliance).first()
		
		# load the form into the appliance object (excluding API token)
		apitoken = appliance.apitoken
		form.populate_obj(appliance)
		appliance.apitoken = apitoken
		
		if form.validate_on_submit():
			# our form validates, so update the database
			appliance.update(appliance)

			# at this point we know the user has entered an Ngrok token (valid form)
			# and we test if the coinbase tokens are working.  if they are, we update
			# the address list and parse it for subdomain information.
			settings = Status().check_settings()
			if settings['coinbase']:
				# sync up addresses with coinbase
				addresses = Addresses()
				addresses.sync(appliance)

				# grab the first address we got from coinbase and use the callback url
				address = db.session.query(Addresses).first()
				if address:
					# overload the appliance's existing subdomain with coinbase address one
					appliance.subdomain = address.subdomain
					appliance.update()
				else:
					# there exists no address with a subdomain, so we keep what we have
					pass

				# build the tunnel config file - ngrok will start after it's built
				appliance.build_tunnel_conf()

			# form was valid, so say thanks	
			response = "Setting have been saved."
			flash(response, "success")

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
	
	# run for either POST or GET
	# check configuration and show messages
	settings = Status().check_settings()

	if settings['token'] == False:
		# show error	
		response = "Please register the API token."
		flash(response, "error")
	
	if settings['coinbase'] == False:
		# show error	
		response = "Please enter valid Coinbase credentials."
		flash(response, "error")

	if settings['ngrok'] == False:
		# show error
		response = "The Ngrok SSL tunnel is NOT running."
		flash(response, "error")

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
	addresses = db.session.query(Addresses).all()

	# render template
	return render_template(
		'configure/addresses.html',
		settings=settings,
		addresses=addresses
	)

# configure instances page
@mod.route('/configure/instances', methods=['GET', 'POST'])
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
