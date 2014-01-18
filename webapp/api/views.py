import re
import os, sys, socket, json
from urllib2 import urlopen
from webapp.libs.geoip import get_geodata
from flask import Blueprint, render_template, flash, redirect, session, url_for, request, g
from flask.ext.login import login_user, logout_user, current_user, login_required
from webapp import app, db, bcrypt, login_manager
from webapp.users.models import User
from webapp.api.models import Images, Flavors
from webapp.configure.models import OpenStack, Appliance
from webapp.libs.openstack import ImageInstall, FlavorInstall

mod = Blueprint('api', __name__)

# remote connection
def server_connect( method = "version" ):
	appliance = db.session.query(Appliance).first()
	url = app.config['APP_WEBSITE'] + 'api/%s?ver=' % method + app.config['VERSION'] + '&apikey=' + appliance.apikey
	response = urlopen(url, timeout=10).read()
	return json.loads(response)

# INSTALL METHODS
@mod.route('/api/images/<int:image_id>/install/', methods=('GET', 'POST'))
@login_required
def images_install(image_id):
	try:
		print "would install flavor %s" % image_id
		return render_template('blank.html')
	except Exception as ex:
		print ex
		return render_template('blank.html')

@mod.route('/api/flavors/<int:flavor_id>/install/', methods=('GET', 'POST'))
@login_required
def flavors_install(flavor_id):
	try:
		print "would install image %s" % flavor_id
		return render_template('blank.html')
	except Exception as ex:
		print ex
		return render_template('blank.html')

# SYNC METHODS
# fetches data from pool operator and populates local tables
@mod.route('/api/images/sync/', methods=('GET', 'POST'))
@login_required
def images_sync():
	try:
		remoteimages = server_connect("images")

		# update the database with the images
		for remoteimage in remoteimages['images']:
			image = db.session.query(Images).filter_by(md5=remoteimage['md5']).first()
			if image is None:
				# we don't have the image coming in from the server
				image = Images()

				# need help here populating db object from dict - anyone?
				image.md5 = remoteimage['md5']
				image.name = remoteimage['name']
				image.url = remoteimage['url']
				image.size = remoteimage['size']
				image.flags = remoteimage['flags']
				image.installed = 0

				# add and commit
				db.session.add(image)
				db.session.commit()
			else:
				# we have the image already, so update
				# need help here populating db object from dict - anyone?
				# hey, it's a fucking POC, alright?
				image.md5 = remoteimage['md5']
				image.name = remoteimage['name']
				image.url = remoteimage['url']
				image.size = remoteimage['size']
				image.flags = remoteimage['flags']
				
				# udpate and commit
				image.update(image)
				db.session.commit()

		return render_template('response.json', response="success")	

	except Exception as ex:
		return render_template('response.json', response="fail on %s" % ex)	

@mod.route('/api/flavors/sync/', methods=('GET', 'POST'))
@login_required
def flavors_sync():
	try:
		remoteflavors = server_connect("flavors")

		# update the database with the flavors
		for remoteflavor in remoteflavors['flavors']:
			flavor = db.session.query(Flavors).filter_by(name=remoteflavor['name']).first()
			if flavor is None:
				# we don't have the flavor coming in from the server
				flavor = Flavors()

				# need help here populating db object from dict - anyone?
				flavor.name = remoteflavor['name']
				flavor.comment = remoteflavor['comment']
				flavor.vpu = remoteflavor['vpu']
				flavor.mem = remoteflavor['mem']
				flavor.disk = remoteflavor['disk']
				flavor.flags = remoteflavor['flags']
				flavor.installed = 0

				# add and commit
				db.session.add(flavor)
				db.session.commit()
			else:
				# we have the flavor already, so update
				# need help here populating db object from dict - anyone?
				flavor.name = remoteflavor['name']
				flavor.comment = remoteflavor['comment']
				flavor.vpu = remoteflavor['vpu']
				flavor.mem = remoteflavor['mem']
				flavor.disk = remoteflavor['disk']
				flavor.flags = remoteflavor['flags']
				
				# udpate and commit
				flavor.update(flavor)
				db.session.commit()

		return render_template('response.json', response="success")	

	except Exception as ex:
		return render_template('response.json', response="fail on %s" % ex)	