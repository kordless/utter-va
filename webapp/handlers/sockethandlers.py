import os
import sys
from urllib2 import urlopen

from flask import Blueprint, render_template, jsonify, flash, redirect, session, url_for, request
from flask.ext.login import login_user, logout_user, current_user, login_required
from flask.ext.socketio import emit

from webapp import app, db, csrf, bcrypt, login_manager, socketio
from webapp.models.models import User, Images, Flavors, Instances, OpenStack, Addresses, Appliance
from webapp.libs.utils import row2dict, server_connect
from webapp.libs.openstack import image_install, image_remove, flavor_install, flavor_remove, instance_start

mod = Blueprint('sockets', __name__)

@socketio.on('connect', namespace='/xovio')
def connect():
	emit('response', {'data': 'connected'}, broadcast=True)

@socketio.on('my event', namespace='/xovio')
def test_message(message):
	print message
	emit('my response', {'data': 'foobar'})