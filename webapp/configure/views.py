import re
import os, sys, socket, json
from urllib2 import urlopen
from webapp.libs.geoip import get_geodata
from flask import Blueprint, render_template, flash, redirect, session, url_for, request, g
from flask.ext.login import login_user, logout_user, current_user, login_required
from webapp import app, db, bcrypt, login_manager
from forms import OpenStackForm
from forms import ApplianceForm
from webapp.users.models import User
from webapp.api.models import Images, Flavors
from webapp.configure.models import OpenStack, Appliance

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
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


# configure instances page
@mod.route('/configure/instances/', methods=('GET', 'POST'))
@login_required
def configure_instances():
	flavors = db.session.query(Flavors).all()
	images = db.session.query(Images).all()
	
	return render_template('configure/instances.html', flavors=flavors, images=images)


# configuration pages
@mod.route('/configure/', methods=('GET', 'POST'))
@login_required
def configure():
	form = ApplianceForm(request.form)
	print form
	if request.method == 'POST':
		if form.validate_on_submit():
			# try to select one and only record
			appliance = db.session.query(Appliance).first()
			
			# delete existing entry
			if appliance:
				appliance.delete()
				db.session.commit()
			
			# create new entry, populate with form, write to db
			appliance = Appliance()
			form.populate_obj(appliance)
			appliance.update(appliance)
			db.session.commit()

			return redirect(url_for(".configure"))

	# get existing form data
	appliance = form.get_appliance()

	# if no geodata, get it
	if not appliance:
		appliance = {}
		geodata = get_geodata()
		appliance['latitude'] = geodata['latitude']
		appliance['longitude'] = geodata['longitude']
	else:
		try:
			lat = float(appliance.latitude)
			lon = float(appliance.longitude)
		except ValueError, TypeError:
			geodata = get_geodata()
			appliance.latitude = geodata['latitude']
			appliance.longitude = geodata['longitude']

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
			flash("File type not allowed or empty.  Try again.")
		
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


