import os
import sys
from urllib2 import urlopen

from flask import Blueprint, render_template, jsonify, flash, redirect, session, url_for, request
from flask.ext.login import login_user, logout_user, current_user, login_required

from webapp import app, db, csrf, bcrypt, login_manager
from webapp.models.models import User, Images, Flavors, Instances, OpenStack, Addresses, Appliance
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

# handler to validate saved token with pool operator
@mod.route('/api/token/validate', methods=('GET', 'POST'))
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

# METHODS USING APITOKEN AUTH
# pool wants us to ping the pool API for something
@csrf.exempt
@mod.route('/api/ping', methods=('GET', 'POST'))
def pool_ping():
	# get the appliance info
	appliance = db.session.query(Appliance).first()

	# build the response
	response = {"response": "success", "result": "ping acknowledged"}

	# check inbound apitoken
	apitoken = request.args.get('apitoken', '')
	if apitoken == appliance.apitoken:
		return jsonify(response)
	else:
		response['response'] = "fail"
		response['result'] = "authorization failed"
		return jsonify(response), 401

# METHODS USING ADDRESS TOKEN AUTH
# handle callback from coinbase on address payment
@csrf.exempt
@mod.route('/api/address/<string:address_token>', methods=('GET', 'POST'))
def address_handler(address_token):
	# look up address
	address = Addresses().get_by_token(address_token)

	# check if we found an address that matches
	if address:
		# find out how much we were paid
		amount = float(request.json['amount'])
		print amount

		# look up how much the flavor for this instance is per hour

		# set the expire time to what has been paid

		# query the instance's desired outcome from the pool

		# take action on the outcome (start/stop)

		print address.address, address.instance_id

		# build the response
		response = {"response": "success", "result": "acknowledged"}
		return jsonify(response)
	
	else:
		response['response'] = "fail"
		response['result'] = "bitcoin address not found"
		return jsonify(response), 401

