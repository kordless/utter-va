import re, os
from urllib2 import urlopen
from flask import Blueprint, render_template, flash, redirect, session, url_for, request, g
from flask.ext.login import login_user, logout_user, current_user, login_required
from webapp import app, db, bcrypt, login_manager
from webapp.users.models import User
from webapp.api.models import Images, Flavors, Instances
from webapp.configure.models import OpenStack, Appliance
from forms import OpenStackForm, ApplianceForm, InstanceForm
from webapp.libs.geoip import get_geodata
from webapp.libs.utils import blockchain_address, generate_token

mod = Blueprint('configure', __name__)

# quote strip
def dequote(string):
	if string.startswith('"') and string.endswith('"'):
		string = string[1:-1]
	return string

# user login callback
@login_manager.user_loader
def load_user(user_id):
	return User.query.get(int(user_id))

ALLOWED_EXTENSIONS = set(['sh'])
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

# configure flavors and images page
@mod.route('/configure/systems/', methods=('GET', 'POST'))
@login_required
def configure_systems():
	flavors = db.session.query(Flavors).all()
	images = db.session.query(Images).all()
	
	return render_template('configure/systems.html', flavors=flavors, images=images)

# configure instances page
@mod.route('/configure/instances/', methods=('GET', 'POST'))
@login_required
def configure_instances():
	form = InstanceForm(request.form)

	flavors = db.session.query(Flavors.osid, Flavors.name, Flavors.active).filter(Flavors.active.in_([1,2])).all()
	images = db.session.query(Images.osid, Images.name, Images.active).filter(Images.active.in_([1,2])).all()
	instances = db.session.query(Instances).all()
	appliance = db.session.query(Appliance).first()

	if request.method == 'POST':
		if form.validate_on_submit():
			instance = Instances()

			# create a token and secret, call blockchain to create callback address
			instance_token = generate_token(size=16, caselimit=True)
			instance_secret = generate_token(size=16, caselimit=False)
			callback_url = "%s/api/instances/%s/payment" % (appliance.serviceurl.strip("/"), instance_token)
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

	return render_template('configure/instances.html', form=form, instances=instances, flavors=flavors, images=images)

# configuration pages
@mod.route('/configure/', methods=('GET', 'POST'))
@login_required
def configure():
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
			db.session.commit()

			# if the ngrok token changed, create a new service url
			if current_ngrok_token != new_ngrok_token:
				appliance.service_url_refresh()
				appliance.update(appliance)
				db.session.commit()

			return redirect(url_for(".configure"))

		else:
			for error in form.paymentaddress.errors:
				flash(error)

	# get existing form data
	appliance = form.get_appliance()

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
		try:
			# just testing the values are correct
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

	return render_template('configure/appliance.html', form=form, appliance=appliance)


@mod.route('/configure/openstack/', methods=('GET', 'POST'))
@login_required
def configure_openstack():
	form = OpenStackForm(request.form)

	if request.method == 'POST':
		# take our file and loop through it grabbing key values
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
			
			# try to select one and only record
			openstack = db.session.query(OpenStack).first()

			# delete existing entry
			if openstack:
				openstack.delete()
				db.session.commit()
			
			# create new entry handle
			openstack = OpenStack()
			
			# set values from extracted lines above - needs SQL injection protection?
			openstack.authurl = "%s" % dequote(keyvals['OS_AUTH_URL']) 
			openstack.tenantname = "%s" % dequote(keyvals['OS_TENANT_NAME']) 
			openstack.tenantid = "%s" % dequote(keyvals['OS_TENANT_ID']) 
			openstack.osusername = "%s" % dequote(keyvals['OS_USERNAME']) 
			openstack.ospassword = "changeme"

			# write it out to database
			db.session.add(openstack)
			db.session.commit()
		
		elif file:
			# file type not allowed
			flash("File type not allowed or empty.  Try again.", 'file-error')
		
		else:
			# user is manually updating form
			if form.validate_on_submit():
				# try to select one and only record
				openstack = db.session.query(OpenStack).first()

				# delete existing entry
				if openstack:
					openstack.delete()
					db.session.commit()
				
				# create new entry, populate with form, write to db
				openstack = OpenStack()
				form.populate_obj(openstack)
				openstack.update(openstack)
				db.session.commit()

				return redirect(url_for(".configure_openstack"))

	# load form and existing openstack settings, if they exist
	openstack = form.get_openstack()
	return render_template('configure/openstack.html', form=form, openstack=openstack)	


