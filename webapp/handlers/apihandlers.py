import os
import sys
from urllib2 import urlopen

from flask import Blueprint, render_template, jsonify, flash, redirect, session, url_for, request
from flask.ext.login import login_user, logout_user, current_user, login_required

from webapp import app, db, bcrypt, login_manager
from webapp.models.models import User, Images, Flavors, Instances, OpenStack, Appliance
from webapp.libs.utils import row2dict, server_connect
from webapp.libs.openstack import image_install, image_remove, flavor_install, flavor_remove, instance_start

mod = Blueprint('api', __name__)

# METHODS USING FULL AUTHENTICATION
# issue new api token to be used with pool operator
@mod.route('/api/token/generate', methods=('GET', 'POST'))
@login_required
def token_generate():
	# update appliance database with a new token
	appliance = db.session.query(Appliance).first()
	appliance.token_refresh()
	appliance.update(appliance)

	return render_template('response.json', response="success")

# pole handler to validate saved token with pool operator
@mod.route('/api/token/check', methods=('GET', 'POST'))
@login_required
def token_validate():
	# update appliance database with a new token
	appliance = db.session.query(Appliance).first()
	
	# check with pool operator
	response = server_connect(method="authorization", apitoken=appliance.apitoken)

	if response['response'] == "success":
		return jsonify(response)
	else:
		return jsonify(response), 401

# METHODS USING TOKEN AUTH
# respond to a pool operator knock
@mod.route('/api/knock/', methods=('GET'))
def operator_knock():
	# get the appliance info
	appliance = db.session.query(Appliance).first()
	
	# check with pool operator
	response = server_connect(method="authorization", apitoken=appliance.apitoken)

	if response['response'] == "success":
		return jsonify(response)
	else:
		return jsonify(response), 401

# deal with adding/removing/viewing instance addresses for deposit
@mod.route('/api/instances/<string:instance_token>/<string:instance_method>', methods=['GET', 'POST'])
def instance_handler(instance_token, instance_method):
	response = {"response": "success", "result": {"payments": "xxxxxxxxxx"}}

	if instance_method == "payment":
		instance = Instances().get_by_token(instance_token)
		instance_start(instance)
	elif instance_method == "detail":
		instance = Instances().get_by_token(instance_token)
		result = {"token": instance.token, "paymentaddress": instance.paymentaddress}
		response['result'] = result

	return jsonify(response)
