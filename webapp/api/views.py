import re
import os, sys, socket, json
from urllib2 import urlopen
from flask import Blueprint, render_template, jsonify, flash, redirect, session, url_for, request, g
from flask.ext.login import login_user, logout_user, current_user, login_required
from webapp import app, db, bcrypt, login_manager
from webapp.users.models import User
from webapp.api.models import Images, Flavors
from webapp.configure.models import OpenStack, Appliance
from webapp.libs.openstack import image_install, flavor_install, flavor_pause, flavor_remove, flavors_installed

mod = Blueprint('api', __name__)

# remote connection
def server_connect( method = "version" ):
	appliance = db.session.query(Appliance).first()
	url = app.config['APP_WEBSITE'] + '/api/%s?ver=' % method + app.config['VERSION'] + '&apitoken=' + appliance.apitoken
	response = urlopen(url, timeout=10).read()
	return json.loads(response)

@mod.route('/api/token/generate/', methods=('GET', 'POST'))
@login_required
def token_generate():
	# update appliance database with a new token
	appliance = db.session.query(Appliance).first()
	appliance.token_refresh()
	appliance.update(appliance)
	db.session.commit()
	return render_template('response.json', response="success")

@mod.route('/api/serviceurl/generate/', methods=('GET', 'POST'))
@login_required
def service_url_generate():
	# update appliance database with a new service url
	appliance = db.session.query(Appliance).first()
	appliance.service_url_refresh()
	appliance.update(appliance)
	db.session.commit()
	return render_template('response.json', response="success")

@mod.route('/api/token/validate/', methods=('GET', 'POST'))
@login_required
def token_validate():
	validate_token = {}
	try:
		validate_token = server_connect('validate')
		if validate_token['response'] == "valid":
			return render_template('response.json', response=validate_token['response'])
		else:
			raise Exception
	except:
		validate_token['response'] = "invalid"
		return render_template('response.json', response=validate_token['response']), 403

# INSTALL METHODS
@mod.route('/api/images/<int:image_id>/<string:image_state>/', methods=('GET', 'POST'))
@login_required
def images_install(image_id, image_state):
	try:
		image = db.session.query(Images).filter_by(id=image_id).first()
		return render_template('blank.html')
	except Exception as ex:
		print ex
		return render_template('blank.html')

@mod.route('/api/flavors/<int:flavor_id>/<string:flavor_state>/', methods=('GET', 'POST'))
@login_required
def flavors_handler(flavor_id, flavor_state):
	try:
		# get the matching flavor
		flavor = db.session.query(Flavors).filter_by(id=flavor_id).first()
		if flavor_state == "remove":
			temp = flavor_remove(flavor)
			flavor.update(temp)
		elif flavor_state == "pause":
			temp = flavor_pause(flavor)
			flavor.update(temp)
		else:
			# tell OpenStack we have a new flavor and set the new osic with result
			temp = flavor_install(flavor)
			flavor.update(temp)
		return render_template('blank.html')
	
	except Exception as ex:
		print ex
		return render_template('blank.html')

@mod.route('/api/openstack/flavors/', methods=('GET', 'POST'))
@login_required
def openstack_flavors():
	flavors = flavors_installed()
	return jsonify(flavors)

# SYNC METHODS
# fetches data from pool operator and populates local tables
@mod.route('/api/images/sync/', methods=('GET', 'POST'))
@login_required
def images_sync():
	try:
		remoteimages = server_connect("images")

		# update images from server
		images = Images()
		images.sync(remoteimages)

		return render_template('response.json', response="success")	

	except Exception as ex:
		return render_template('response.json', response="fail on %s" % ex)	

@mod.route('/api/flavors/sync/', methods=('GET', 'POST'))
@login_required
def flavors_sync():
	try:
		remoteflavors = server_connect("flavors")

		# update flavors from server
		flavors = Flavors()
		flavors.sync(remoteflavors)
			
		# do a pass to update the flavor database
		flavors = flavors_installed()
		return jsonfiy(flavors)

	except Exception as ex:
		return render_template('response.json', response="fail on %s" % ex)	