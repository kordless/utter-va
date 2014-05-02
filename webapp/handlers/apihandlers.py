import os
import sys
from urllib2 import urlopen

from flask import Blueprint, render_template, jsonify, flash, redirect, session, url_for, request
from flask.ext.login import login_user, logout_user, current_user, login_required

from webapp import app, db, csrf, bcrypt, socketio, login_manager

from webapp.models.models import User, Appliance, Status
from webapp.models.models import Images, Flavors, OpenStack
from webapp.models.models import Instances, Addresses

from webapp.libs.utils import row2dict, message
from webapp.libs.pool import pool_api_connect

from webapp.libs.openstack import image_install, image_remove 
from webapp.libs.openstack import flavor_install, flavor_remove
from webapp.libs.openstack import instance_start

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
	
	# flush the cached status
	Status().flush()

	return render_template('response.json', response="success")

# handler to validate saved token with pool operator
@mod.route('/api/token/validate', methods=('GET', 'POST'))
@login_required
def token_validate():
	# update appliance database with a new token
	appliance = db.session.query(Appliance).first()
	
	# check with pool operator
	response = pool_api_connect(method="authorization", apitoken=appliance.apitoken)

	if response['response'] == "success":
		# flush the cached status
		Status().flush()
		return jsonify(response)
	else:
		return jsonify(response), 401

@csrf.exempt
@mod.route('/api/oof', methods=('GET', 'POST'))
def message2():
	print "testing"
	return ""

# METHODS USING APITOKEN AUTH
# api for sending messages into the socketio context
@csrf.exempt
@mod.route('/api/message', methods=('GET', 'POST'))
def message():
	# get the appliance info
	appliance = db.session.query(Appliance).first()

	# build the response
	response = {"response": "", "result": {}}

	# check apitoken matches
	apitoken = request.args.get('apitoken', '')
	if apitoken == appliance.apitoken:
		message = request.args.get('text', 'no message')
		status = request.args.get('status', 'success')
		reloader = request.args.get('reload', 'false')
		if reloader == 'true' or reloader == '1':
			reloader = True
		else:
			reloader = False
		
		response['response'] = status
		response['result'] = {"message": message, "reload": reloader}
		socketio.emit('message', {"data": response}, namespace='/xovio')
		return jsonify(response)
	else:
		response['response'] = "fail"
		response['result'] = "apitoken is invalid"
		return jsonify(response), 401

# METHODS USING ADDRESS TOKEN AUTH
# handle callback from coinbase on address payment
@csrf.exempt
@mod.route('/api/address/<string:address_token>', methods=('GET', 'POST'))
def address_handler(address_token):
	# look up address
	address = Addresses().get_by_token(address_token)

	# build the response
	response = {"response": "success", "result": {}}

	# check if we found an address that matches
	if address:
		# pull the instance out by id
		instance = Instances().get_by_id(address.instance_id)

		try:
			# find out how much we were paid
			amount = float(request.json['amount'])
		except:
			# bad stuff happens
			response['response'] = "fail"
			response['result'] = "payment amount required"		
			return jsonify(response), 401

		# update the instance's state to starting (state == 2)
		instance.state = 2
		instance.update()

		# indicate we were paid and reload the page
		message("Instance %s received a payment of %s." % (amount, instance.name), status="success", reloader=True)

		# everything else related to starting the instance is handled by a cron job

		# load response
		response['result'] = "acknowledged"
		return jsonify(response)
		
	else:
		app.logger.info("A payment was recieved on an unused bitcoin address.")
		response['response'] = "fail"
		response['result'] = "bitcoin address token not found"		
		return jsonify(response), 401
