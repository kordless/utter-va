import os
import sys
from urllib2 import urlopen

from flask import Blueprint, render_template, jsonify, flash, redirect, session, url_for, request, g
from flask.ext.login import login_user, logout_user, current_user, login_required

from webapp import app, db, bcrypt, login_manager
from webapp.users.models import User
from webapp.api.models import Images, Flavors
from webapp.configure.models import OpenStack, Appliance
from webapp.libs.utils import row2dict
from webapp.libs.openstack import image_install, image_detail, image_remove, images_cleanup, flavor_install, flavor_remove, flavors_cleanup

mod = Blueprint('api', __name__)

# TOKEN METHODS
# issue new tokens and proxy validation to pool operator
@mod.route('/api/token/generate', methods=('GET', 'POST'))
@login_required
def token_generate():
	# update appliance database with a new token
	appliance = db.session.query(Appliance).first()
	appliance.token_refresh()
	appliance.update(appliance)

	return render_template('response.json', response="success")

@mod.route('/api/token/validate', methods=['GET', 'POST'])
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

# INSTANCE ADDRESS METHODS
# deal with adding/removing/viewing instance addresses for deposit
@mod.route('/api/instances/<int:address_id>/<string:address_method>', methods=['GET', 'POST'])
# login credentials are not required for these methods
# if ngrok is used, security is provided by http auth set in the ngrok config
def address_handler(address_id, address_state):
	# get the matching image
	image = db.session.query(Images).filter_by(id=image_id).first()
	if image_state == "remove":
		result = image_remove(image)
	elif image_state == "detail":
		result = image_detail(image)
	else:
		# tell OpenStack we have a new image and set image active in db
		result = image_install(image)
	
	return jsonify({"response": result['response'], "image": row2dict(result['image'])})


# SYSTEM METHODS
# deal with adding/removing/viewing images and flavors
@mod.route('/api/images/<int:image_id>/<string:image_method>', methods=['GET', 'POST'])
@login_required
def images_handler(image_id, image_method):
	# get the matching image
	image = db.session.query(Images).filter_by(id=image_id).first()
	if image_method == "remove":
		result = image_remove(image)
	elif image_method == "detail":
		result = image_detail(image)
	else:
		# tell OpenStack we have a new image and set image active in db
		result = image_install(image)
	
	return jsonify({"response": result['response'], "image": row2dict(result['image'])})

@mod.route('/api/flavors/<int:flavor_id>/<string:flavor_method>', methods=['GET', 'POST'])
@login_required
def flavors_handler(flavor_id, flavor_method):
	# get the matching flavor
	flavor = db.session.query(Flavors).filter_by(id=flavor_id).first()
	if flavor_method == "remove":
		result = flavor_remove(flavor)
	else:
		# tell OpenStack we have a new flavor and set the new osic with result
		result = flavor_install(flavor)

	return jsonify({"response": result['response'], "flavor": row2dict(result['flavor'])})

# SYNC METHODS
# fetches data from pool operator and populates local tables
@mod.route('/api/images/sync', methods=['GET'])
@login_required
def images_sync():
	appliance = db.session.query(Appliance).first()

	# update images from server
	images = Images()
	response = images.sync(appliance.apitoken)

	if response['response'] == "success":
	# do a pass to audit the images database with OpenStack's images
		cleanup_response = images_cleanup(images.get_all())

	return jsonify(response)	

@mod.route('/api/flavors/sync', methods=['GET'])
@login_required
def flavors_sync():
	appliance = db.session.query(Appliance).first()

	# update flavors from server
	flavors = Flavors()
	response = flavors.sync(appliance.apitoken)

	if response['response'] == "success":
		# do a pass to audit the flavors database with OpenStack's flavors
		cleanup_response = flavors_cleanup(flavors.get_all())
		print cleanup_response

	return jsonify(response)