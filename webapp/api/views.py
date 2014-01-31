import re
import os, sys, socket, json
from urllib2 import urlopen
from flask import Blueprint, render_template, jsonify, flash, redirect, session, url_for, request, g
from flask.ext.login import login_user, logout_user, current_user, login_required
from webapp import app, db, bcrypt, login_manager
from webapp.users.models import User
from webapp.api.models import Images, Flavors
from webapp.configure.models import OpenStack, Appliance
from webapp.libs.openstack import image_install, image_detail, image_remove, images_cleanup, flavor_install, flavor_remove, flavors_cleanup

mod = Blueprint('api', __name__)

def row2dict(row):
    d = {}
    for column in row.__table__.columns:
        d[column.name] = getattr(row, column.name)

    return d

# remote connection
def server_connect( method = "version" ):
	appliance = db.session.query(Appliance).first()
	url = app.config['APP_WEBSITE'] + '/api/%s?ver=' % method + app.config['VERSION'] + '&apitoken=' + appliance.apitoken
	response = urlopen(url, timeout=10).read()
	return json.loads(response)

@mod.route('/api/token/generate', methods=('GET', 'POST'))
@login_required
def token_generate():
	# update appliance database with a new token
	appliance = db.session.query(Appliance).first()
	appliance.token_refresh()
	appliance.update(appliance)
	db.session.commit()
	return render_template('response.json', response="success")

@mod.route('/api/serviceurl/generate', methods=('GET', 'POST'))
@login_required
def service_url_generate():
	# update appliance database with a new service url
	appliance = db.session.query(Appliance).first()
	appliance.service_url_refresh()
	appliance.update(appliance)
	db.session.commit()
	return render_template('response.json', response="success")

@mod.route('/api/token/validate', methods=('GET', 'POST'))
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
@mod.route('/api/instances/<int:address_id>/<string:address_method>', methods=('GET', 'POST'))
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


# CLUSTER METHODS
# deal with adding/removing/viewing images and flavors
@mod.route('/api/images/<int:image_id>/<string:image_method>', methods=('GET', 'POST'))
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

@mod.route('/api/flavors/<int:flavor_id>/<string:flavor_method>', methods=('GET', 'POST'))
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
	try:
		remoteimages = server_connect("images")

		# update images from server
		images = Images()
		images.sync(remoteimages)

		# do a pass to cleanup the images database
		results = images_cleanup()

		# return the list of images
		return jsonify(results)

	except Exception as ex:
		response = "fail on %s" % ex

	return jsonify({"response": response})	

@mod.route('/api/flavors/sync', methods=['GET'])
@login_required
def flavors_sync():
	try:
		remoteflavors = server_connect("flavors")

		# update flavors from server
		flavors = Flavors()
		flavors.sync(remoteflavors)

		# do a pass to cleanup the flavor database
		flavors = flavors_cleanup()
		return jsonify(flavors)

	except Exception as ex:
		response = "fail on %s" % ex

	return jsonify({"response": response})