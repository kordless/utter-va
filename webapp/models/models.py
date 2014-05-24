import os
import yaml
import shutil
import json
import time
import md5

from urlparse import urlparse

from keystoneclient.v2_0 import client as keyclient
from flask.ext.login import UserMixin

from werkzeug import generate_password_hash, check_password_hash

from webapp import app
from webapp import db
from webapp import bcrypt

from webapp.models.mixins import CRUDMixin
from webapp.libs.coinbase import coinbase_generate_address, coinbase_get_addresses, coinbase_checker
from webapp.libs.pool import pool_api_instances, pool_api_connect
from webapp.libs.utils import generate_token, row2dict, ngrok_checker, message
from webapp.libs.images import uninstall_image
from webapp.libs.geoip import get_geodata

# user model
class User(UserMixin, CRUDMixin,  db.Model):
	__tablename__ = 'users'
	id = db.Column(db.Integer, primary_key=True)
	username = db.Column(db.String(100), unique=True)
	password = db.Column(db.String(100), unique=True)

	def __init__(self, username=None, password=None):
			self.username = username
			self.password = password

	def __repr__(self):
			return '<Username %r>' % (self.username)


# address model
class Addresses(CRUDMixin, db.Model):
	__tablename__ = 'addresses'
	id = db.Column(db.Integer, primary_key=True)
	address = db.Column(db.String(100))
	token = db.Column(db.String(100))
	instance_id = db.Column(db.Integer, db.ForeignKey('instances.id'))
	subdomain = db.Column(db.String(100))

	# relationship to instances
	instance = db.relationship('Instances', foreign_keys='Addresses.instance_id')

	def __init__(self,
		address=None,
		token=None,
		instance_id=None,
		subdomain=None
	):
		self.address = address
		self.token = token
		self.instance_id = instance_id
		self.subdomain = subdomain

	def __repr__(self):
		return '<Address %r>' % (self.address)
	
	def get_by_token(self, token):
		address = db.session.query(Addresses).filter_by(token=token).first()
		return address

	def sync(self, appliance):
		# grab image list from pool server
		response = coinbase_get_addresses(appliance=appliance)

		if response['response'] == "success":
			remoteaddresses = response['result']['addresses']

			# update database for with remote addresses
			for remoteaddress_address in remoteaddresses:
				# work around coinbase's strange address:address thing
				remoteaddress = remoteaddress_address['address']

				# check if address label is the md5 of our coinbase api key
				if remoteaddress['label'] == md5.new(appliance.cbapikey).hexdigest():

					# see if we have a matching image
					address = db.session.query(Addresses).filter_by(address=remoteaddress['address']).first()
					
					# we don't have the address at coinbase in database
					if address is None:
						# create a new image
						address = Addresses()
						address.address = remoteaddress['address']
						address.token = urlparse(remoteaddress['callback_url']).path.split('/')[-1]
						address.instance_id = 0 # no instances yet
						address.subdomain = urlparse(remoteaddress['callback_url']).hostname.split('.')[0]

						# add and commit
						address.update(address)

					# we have the address already and need to update it
					else:
						# update address from remote images
						address.address = remoteaddress['address']
						address.token = urlparse(remoteaddress['callback_url']).path.split('/')[-1]
						address.subdomain = urlparse(remoteaddress['callback_url']).hostname.split('.')[0]

						# add and commit
						address.update(address)

				else:
					# must be another appliance's address so skip it
					pass

			# overload the results with the list of current addresses
			response['result']['addresses'] = []
			addresses = db.session.query(Addresses).all()

			for address in addresses:
				response['result']['addresses'].append(row2dict(address))

			return response

		# failure contacting server
		else:
			# lift respose from server call to view
			return response

	# assign a bitcoin address for use with an instance
	def assign(self, instance_id):
		# check if the instance id is already assigned to an address (just in case)
		address = db.session.query(Addresses).filter_by(instance_id=instance_id).first()
		
		# appliance object
		appliance = db.session.query(Appliance).first()

		# if we found an address, just return it
		if address:
			return address
		else:
			# check if we have an empty address to assign
			address = db.session.query(Addresses).filter_by(instance_id=0).first()		
			
			# we found one, so assign instance_id, appliance subdomain
			if address:
				# assign the instance id to the address
				address.instance_id = instance_id
				# leave the subdomain alone from the sync
				# address.subdomain
				address.update(address)
				return address

			else:
				# ask coinbase for new address and set callback
				token = generate_token(size=16, caselimit=True)
				callback_url = "https://%s.%s/api/address/%s" % (
					appliance.subdomain, 
					app.config['POOL_SSL_PROXY_DOMAIN'], 
					token
				)
				label = md5.new(appliance.cbapikey).hexdigest()
				response = coinbase_generate_address(appliance, callback_url, label)

				# create new address in db
				if response['response'] == "success":
					address = Addresses()
					address.address = response['result']['address']
					address.token = token
					address.instance_id = instance_id
					address.subdomain = appliance.subdomain
					address.update()

					return address
				else:
					# something went wrong with coinbase
					# return 0 and let calling code handle it
					return None

	# release a bitcoin address back into pool
	def release(self):
		# now change the instance to indicate it's available
		self.instance_id = 0
		self.update(self)
		return self
		

# instance model
class Instances(CRUDMixin, db.Model):
	__tablename__ = 'instances'
	id = db.Column(db.Integer, primary_key=True)
	created = db.Column(db.Integer)
	updated = db.Column(db.Integer) 
	expires = db.Column(db.Integer)
	name = db.Column(db.String(100))
	osid = db.Column(db.String(100))
	poolid = db.Column(db.String(100))
	privateipv4 = db.Column(db.String(100))
	publicipv4 = db.Column(db.String(100))
	publicipv6 = db.Column(db.String(100))
	ssltunnel = db.Column(db.String(400))

	state = db.Column(db.Integer) 
	# instance state is one of:
	# 0 - inactive (frozen)
	# 1 - payment address available (thaw)
	# 2 - payment observed from callback (light)
	# 3 - instance starting (warm)
	# 4 - instance running (hot)
	# 5 - instance suspended (cooling)
	# 6 - payment observed from callback and unsuspend (relight)
	# 7 - instance decommissioned (removed)
	
	sshkey = db.Column(db.String(2048))
	callback_url = db.Column(db.String(1024))

	# foreign keys
	flavor_id = db.Column(db.Integer, db.ForeignKey('flavors.id'))
	image_id = db.Column(db.Integer, db.ForeignKey('images.id'))
	address_id = db.Column(db.Integer, db.ForeignKey('addresses.id'))

	# relationships
	flavor = db.relationship('Flavors', foreign_keys='Instances.flavor_id')
	image = db.relationship('Images', foreign_keys='Instances.image_id')
	address = db.relationship('Addresses', foreign_keys='Instances.address_id')

	def __init__(self, 
		created=None,
		updated=None,
		expires=None,
		name=None,
		osid=None,
		poolid=None,
		privateipv4=None,
		publicipv4=None,
		publicipv6=None,
		ssltunnel=None,
		state=None,
		sshkey=None,
		callback_url=None,
		flavor_id=None,
		image_id=None,
		address_id=None
	):
		self.created = created
		self.updated = updated
		self.expires = expires
		self.name = name
		self.osid = osid
		self.poolid = poolid
		self.privateipv4 = privateipv4
		self.publicipv4 = publicipv4
		self.publicipv6 = publicipv6
		self.ssltunnel = ssltunnel
		self.state = state
		self.sshkey = sshkey
		self.callback_url = callback_url
		self.flavor_id = flavor_id
		self.image_id = image_id
		self.address_id = address_id

	def toggle(self, flavor_id, active):
		# set active/inactive state for instances with a given flavor_id
		# we only set instances that are in state 0 - inactive, or 1 - waiting on payment
		state = 0 if int(active) == 1 else 1
		instances = db.session.query(Instances).filter_by(flavor_id=flavor_id, state=state).all()

		# set to active/inactive
		for instance in instances:
			instance.state = int(active)
			instance.update()

		return True

	# whip up a nice instance for receiving payments
	def mix(self, flavor):
		# build response
		response = {"response": "success", "result": {"message": "", "instance": {}}}

		# the first instance which has this flavor assigned but is not running (active == 1)
		instance = db.session.query(Instances).filter_by(flavor_id=flavor.id, state=1).first()

		# startable instance NOT available for this flavor, so create a warm one
		if not instance:
			# create a new instance		
			instance = Instances()
			instance.name = "smi-%s" % generate_token(size=8, caselimit=True)
			instance.flavor_id = flavor.id

			# grab the first available image for a holder for the warm instance
			image = db.session.query(Images).first()
			instance.image_id = image.id

			# timestamps
			epoch_time = int(time.time())
			instance.created = epoch_time
			instance.updated = epoch_time
			instance.expires = epoch_time # already expired

			# set state
			instance.state = 1 # has address, but no payments/not started (warm)

			# update - provides instance.id to us
			instance.update()

			# finally, assign a bitcoin address
			addresses = Addresses()
			instance.address = addresses.assign(instance.id)	
			instance.update()

			response['result']['message'] = "Created new instance and assigned address."
		
		else:
			# found an instance - make sure we have an address assigned to it
			if not instance.address:
				instance.address = Addresses().assign(instance.id)
				instance.update()
				response['result']['message'] = "Found instance and assigned address."
			else:
				response['result']['message'] = "Found instance and address."

		# overload the results with the list of current instances
		response['result']['instance'] = instance
		return response

	# receive a payment on an instance or allow a zero payment short start
	def coinop(self, amount):
		# build response
		response = {"response": "success", "result": {"message": "", "instance": {}}}

		# calculate the purchased seconds based on payment we received
		ask = float(self.flavor.ask)/1000000 # BTC per hour
		
		try:
			purchased_seconds = (amount/ask)*3600 # amount in BTC/ask in BTC * seconds in hour
		except:
			purchased_seconds = 0

		# handle local appliance start
		if amount == 0:
			purchased_seconds = 15*60 # give 15 minutes to instance for free

		# current UTC time in seconds since epoch
		epoch_time = int(time.time())

		# if we're not running (state==1), set the run state to light (to be started)
		# if we're suspended (state==5), set the run state to relight (to be unsuspended)
		# cron jobs will take care of the rest of the job of starting/unsuspending
		# NOTE: We're getting paid pennies for doing nothing until cronjob runs!
		if self.state == 1: 
			self.state = 2
			self.expires = epoch_time + purchased_seconds # starting from now
		elif self.state == 5:
			self.state = 6
			self.expires = epoch_time + purchased_seconds # starting from now
		else:
			# states 0, 2, 3, 4, 6, 7
			self.expires = self.expires + purchased_seconds # starting from expire time

		# update the instance
		self.update()

		# response
		response['result']['message'] = "Added %s seconds to %s's expire time." % (purchased_seconds, self.name)
		response['result']['instance'] = row2dict(self)
		return response

	# move instances from light to warm
	def start(self):
		from webapp.libs.openstack import flavor_verify_install
		from webapp.libs.openstack import image_verify_install
		from webapp.libs.openstack import instance_start
	
		# build the response
		response = {"response": "success", "result": {"message": "", "instance": {}}}

		# appliance
		appliance = Appliance().get()

		# make a call to the pool for the instance details
		pool_response = pool_api_instances(self, appliance.apitoken)
		if pool_response['response'] == "fail":
			return pool_response

		# overload the response from the server into the instance settings
		# do something with response - TODO
		# how do we do a dynamic image?
		# sshkey, post creation script, security rules

		# take the image and verify install
		image = Images().get_by_id(self.image.id)
		osimage = image_verify_install(image)

		# take the flavor and verify install
		flavor = Flavors().get_by_id(self.flavor.id)
		osflavor = flavor_verify_install(flavor)

		# handle failures of either flavor or image
		if osimage['response'] == 'fail':
			response['response'] = "fail"
			response['result']['message'] = "Failed to create image."
			return response
		if osflavor['response'] == 'fail':
			response['response'] = "fail"
			response['result']['message'] = "Failed to create flavor."
			return response

		# start the instance and set state
		epoch_time = int(time.time())
		if self.expires > epoch_time:
			cluster_response = instance_start(self)
			
			# process response
			if cluster_response['response'] == "success":
				server = cluster_response['result']['server']
				self.osid = server.id # assign openstack instance id
				self.state = 3 # mark as starting
				self.update()
				response['result'] = cluster_response['result']
			else:
				response = cluster_response
		else:
			# instance time expired, so don't start
			self.state = 1
			self.update()
			response['response'] = "fail"
			response['result']['message'] = "Instance payment is expired.  Now waiting on payment."

		return response

	# returns information about an instance once it moves to ACTIVE state
	# sets information about the instance and does a callback with info
	def nudge(self):
		from webapp.libs.openstack import instance_info

		# get instance (server) info
		response = instance_info(self)

		# set instance meta data
		if response['response'] == "success":
			server = response['result']['server']

			# if the state is ACTIVE, we set to be running state==4
			if server.status == "ACTIVE":
			# set network info
			# make RUNNING callback
				self.state = 4
				self.update()
			else:
				response['response'] = "fail"
				response['message'] = "Server isn't in active state yet."

			# notify the pool server of update
			updated = False
			if updated:
				pass

		return response

	# HOUSEKEEPING WORKS ON STATE==4 and STATE==5 INSTANCES ONLY
  # pauses instances which are payment expired
  # decomissions instances which are past paused grace period
	# starts instances which should be running and aren't expired
	# decomissions non-running instances which are payment expired
	def housekeeping(self):
		from webapp.libs.openstack import instance_info
		from webapp.libs.openstack import instance_suspend
		from webapp.libs.openstack import instance_resume
		from webapp.libs.openstack import instance_decommission

		# build the response
		response = {"response": "success", "result": {"message": "", "server": {}}}

		# get instance (server) info
		cluster_response = instance_info(self)
		server = cluster_response['result']['server']

		# we all have limited time in this reality
		epoch_time = int(time.time())

		# debugging
		print server.status
		print epoch_time
		print self.expires

		# this is complicated...because we aren't EC with OpenStack
		if cluster_response['response'] == "success": 
			# openstack responded it found this instance
			if server.status == "ACTIVE":
				# openstack says the server is running
				if self.expires < epoch_time:
					# suspend the instance for non-payment
					response = instance_suspend(self)
					response['result']['message'] = "Instance %s suspended." % self.name
					self.state = 5
			elif server.status == "SUSPENDED":
				# openstack says this instance is suspended
				if self.expires > epoch_time:
					# should be running because not expired
					response = instance_resume(self)
					response['result']['message'] = "Instance %s resumed." % self.name
					self.state = 3 # mark as starting		
				if self.expires + 200 < epoch_time:
					# should be destroyed (suspended for +2 hours without pay)
					response['result']['message'] = "Instance %s decommissioned." % self.name
					self.state = 7		
			else:
				# openstack indicates another state besides SUSPENDED or ACTIVE
				if self.expires > epoch_time:
					# we should be running, but in a weird state - destroy then restart
					response = instance_decommission(self)
					response['result']['message'] = "Instance %s restarted." % self.name
					self.state = 2 # set as paid and ready to start
		else:
			# openstack can't find this instance
			if self.expires > epoch_time:
				# set instance to restart - not expired, should be running
				response['response'] = "fail" # technically, this shouldn't happen
				response['result']['message'] = "Setting instance %s to restart." % self.name
				self.state = 2 # will be started shortly after this by start
			else:
				# no reason to be running
				response['response'] = "fail"
				response['result']['message'] = "Instance %s decommissioned." % self.name
				self.state = 7 # will be deleted shortly after this by trashman

		# update
		self.update()

		return response

	# delete and cleanup instances which have been decomissioned
	def trashman(self):
		from webapp.libs.openstack import instance_info
		from webapp.libs.openstack import instance_suspend
		from webapp.libs.openstack import instance_resume
		from webapp.libs.openstack import instance_decommission		

		# build the response
		response = {"response": "success", "result": {"message": "", "server": {}}}

		# get instance (server) info
		cluster_response = instance_info(self)

		if cluster_response['response'] == "success":
			# we should NOT have this, so try to decomission out of desperation
			cluster_response = instance_decommission(self)
			response['result']['message'] = "Asking OpenStack to terminate instance %s" % self.name
		else:
			# delete this instance into forever
			address = Addresses().get_by_id(self.address_id)
			address.release()
			self.delete(self)
			response['result']['message'] = "Instance %s has been deleted." % self.name

		return response

	def __repr__(self):
		return '<Instance %r>' % (self.name)


# images model
class Images(CRUDMixin, db.Model):
	__tablename__ = 'images'
	id = db.Column(db.Integer, primary_key=True)
	osid = db.Column(db.String(100))
	created = db.Column(db.Integer)
	updated = db.Column(db.Integer)
	name = db.Column(db.String(100), unique=True)
	description = db.Column(db.String(200))
	url = db.Column(db.String(1024), unique=True)
	local_url = db.Column(db.String(1024), unique=True)
	diskformat = db.Column(db.String(100))
	containerformat = db.Column(db.String(100))
	size = db.Column(db.Integer)

	# 8 - uninstall
	flags = db.Column(db.Integer)

	# 0 - not installed/error, 1 - know about it, 2 - installing, 3 - installed
	active = db.Column(db.Integer)

	def __init__(
		self, 
		osid=None,
		created=None,
		updated=None,
		name=None, 
		description=None, 
		url=None,
		local_url=None,
		size=None, 
		diskformat=None, 
		containerformat=None, 
		flags=None
	):
		self.osid = osid
		self.created = created
		self.updated = updated
		self.name = name
		self.description = description
		self.url = url
		self.local_url = local_url
		self.size = size
		self.diskformat = diskformat
		self.containerformat = containerformat
		self.flags = flags
	
	def __repr__(self):
		return '<Image %r>' % (self.name)

	def check(self):
		images = db.session.query(Images).all()

		# minimum one image installed?
		image_active = False

		for image in images:
			if image.active:
				image_active = True

		return image_active

	def sync(self, appliance):
		# grab image list from pool server
		response = pool_api_connect(method="images", apitoken=appliance.apitoken)

		if response['response'] == "success":
			remoteimages = response['result']
					
			# update database for images
			for remoteimage in remoteimages['images']:
				# see if we have a matching image
				image = db.session.query(Images).filter_by(name=remoteimage['name']).first()
				
				# check if we need to delete image from local db
				# b'001000' indicates delete image
				# TODO: need to cleanup OpenStack images if we uninstall
				if (remoteimage['flags'] & 8) == 8:
					# only delete if we have it
					if image is not None:
						# try to delete the local copy
						uninstall_image(image)

						# remove the image from the database
						image.delete(image)
					else:
						# we don't have it, so we do nothing
						pass

				# we don't have the image coming in from the server, so install
				elif image is None:
					# create a new image
					image = Images()
					epoch_time = int(time.time())
					image.created = epoch_time
					image.updated = epoch_time
					image.name = remoteimage['name']
					image.description = remoteimage['description']
					image.url = remoteimage['url']
					image.size = remoteimage['size'] # used as a suggestion of size only
					image.diskformat = remoteimage['diskformat']
					image.containerformat = remoteimage['containerformat']
					image.active = 1 # indicates we know about it, but not downloaded
					image.flags = remoteimage['flags']

					# add and commit
					image.update(image)

				else:
					# update image from remote images (local lookup was by name)
					epoch_time = int(time.time())
					image.description = remoteimage['description']
					if image.url != remoteimage['url']:
						image.url = remoteimage['url']
						image.updated = epoch_time
					if image.diskformat != remoteimage['diskformat']:
						image.diskformat = remoteimage['diskformat']
						image.updated = epoch_time
					if image.containerformat != remoteimage['containerformat']:
						image.containerformat = remoteimage['containerformat']
						image.updated = epoch_time
					if image.flags != remoteimage['flags']:
						image.flags = remoteimage['flags']
						image.updated = epoch_time

					# update
					image.update(image)

			# grab a new copy of the images in database
			images = db.session.query(Images).all()

			# overload the results with the list of current flavors
			response['result']['images'] = []
			images = db.session.query(Images).all()

			for image in images:
				response['result']['images'].append(row2dict(image))

			return response

		# failure contacting server
		else:
			# lift respose from server call to view
			return response


# flavors model
class Flavors(CRUDMixin,  db.Model):
	__tablename__ = 'flavors'
	id = db.Column(db.Integer, primary_key=True)
	osid = db.Column(db.String(100))
	name = db.Column(db.String(100), unique=True)
	description = db.Column(db.String(200))
	vpus = db.Column(db.Integer)
	memory = db.Column(db.Integer)
	disk = db.Column(db.Integer)
	network = db.Column(db.Integer)
	rate = db.Column(db.Integer)
	ask = db.Column(db.Integer)
	launches = db.Column(db.Integer)
	flags = db.Column(db.Integer)
	active = db.Column(db.Integer)

	def __init__(
		self, 
		name=None, 
		osid=None, 
		description=None, 
		vpus=None, 
		memory=None, 
		disk=None, 
		network=None, 
		rate=None, 
		ask=None, 
		launches=None, 
		flags=None, 
		active=None
	):
		self.name = name
		self.osid = osid
		self.description = description
		self.vpus = vpus
		self.memory = memory
		self.disk = disk
		self.network = network
		self.rate = rate
		self.ask = ask
		self.launches = launches
		self.flags = flags
		self.active = active

	def __repr__(self):
		return '<Flavor %r>' % (self.name)

	def check(self):
		flavors = db.session.query(Flavors).all()

		# minimum one flavor installed?
		flavors_active = 0
		for flavor in flavors:
			if flavor.active:
				flavors_active =+ 1

		return flavors_active

	def sync(self, appliance):
		# grab image list from pool server
		response = pool_api_connect(method="flavors", apitoken=appliance.apitoken)

		# remote sync
		if response['response'] == "success":
			remoteflavors = response['result']

			# update the database with the flavors
			for remoteflavor in remoteflavors['flavors']:
				flavor = db.session.query(Flavors).filter_by(name=remoteflavor['name']).first()

				# check if we need to delete flavor from local db
				# b'001000' indicates delete image
				# TODO: need to cleanup OpenStack flavor if we uninstall
				if (remoteflavor['flags'] & 8) == 8:
					# only delete if we have it
					if flavor is not None:
						# remove the flavor from the database
						flavor.delete(flavor)
					else:
						# we don't have it, so we do nothing
						pass

				elif flavor is None:
					# we don't have the flavor coming in from the server
					flavor = Flavors()

					# create a new flavor
					flavor.name = remoteflavor['name']
					flavor.description = remoteflavor['description']
					flavor.vpus = remoteflavor['vpus']
					flavor.memory = remoteflavor['memory']
					flavor.disk = remoteflavor['disk']
					flavor.network = remoteflavor['network']
					flavor.rate = remoteflavor['rate']
					flavor.ask = remoteflavor['rate'] # set ask to market rate
					flavor.launches = remoteflavor['launches']
					flavor.flags = remoteflavor['flags']
					flavor.active = 1

					# add and commit
					flavor.update(flavor)

				# we have the flavor and need to update it	
				else:
					# we have the flavor already, so update
					flavor.name = remoteflavor['name']
					flavor.description = remoteflavor['description']
					flavor.vpus = remoteflavor['vpus']
					flavor.memory = remoteflavor['memory']
					flavor.disk = remoteflavor['disk']
					flavor.network = remoteflavor['network']
					flavor.rate = remoteflavor['rate']
					# we leave flavor.ask alone
					# we leave flavor.active alone
					flavor.launches = remoteflavor['launches']
					flavor.flags = remoteflavor['flags']
					
					# update
					flavor.update(flavor)

			# overload the results with the list of current flavors
			response['result']['flavors'] = []
			flavors = db.session.query(Flavors).all()
			for flavor in flavors:
				response['result']['flavors'].append(row2dict(flavor))
			return response

		# failure contacting server
		else:
			# lift the response from server to view
			return response


# openstack model
class OpenStack(CRUDMixin, db.Model):
	__tablename__ = 'openstack'
	id = db.Column(db.Integer, primary_key=True)

	authurl = db.Column(db.String(100))
	tenantname = db.Column(db.String(100), unique=True)
	tenantid = db.Column(db.String(100), unique=True)
	osusername = db.Column(db.String(100), unique=True)
	ospassword = db.Column(db.String(100))
 
	def __init__(
		self, 
		authurl=None, 
		tenantname=None, 
		tenantid=None, 
		osusername=None, 
		ospassword=None
	):
		self.authurl = authurl
		self.tenantname = tenantname
		self.tenantid = tenantid
		self.osusername = osusername
		self.ospassword = ospassword

	def __repr__(self):
		return '<TenantID %r>' % (self.tenantid)

	# check we are good to talk to openstack 
	def check(self):
		openstack = db.session.query(OpenStack).first()

		if openstack:
			try:
				keystone = keyclient.Client(
					username = openstack.osusername,
					password = openstack.ospassword,
					tenant_id = openstack.tenantid,
					auth_url = openstack.authurl,
					timeout = 5
				)
			except:
				return False
		else:
			return False
		
		return True


# appliance model
class Appliance(CRUDMixin, db.Model):
	__tablename__ = 'appliance'
	id = db.Column(db.Integer, primary_key=True)
	apitoken = db.Column(db.String(100), unique=True)
	ngroktoken = db.Column(db.String(100), unique=True)
	subdomain = db.Column(db.String(100), unique=True)
	dynamicimages = db.Column(db.Integer)
	secret = db.Column(db.String(100), unique=True)
	cbapikey = db.Column(db.String(100), unique=True)
	cbapisecret = db.Column(db.String(100), unique=True)
	latitude = db.Column(db.String(100), unique=True)
	longitude = db.Column(db.String(100), unique=True)
	local_ip = db.Column(db.String(100), unique=True)

	def __init__(
		self, 
		apitoken=None, 
		ngroktoken=None, 
		subdomain=None, 
		dynamicimages=None, 
		secret=None, 
		cbapikey=None, 
		cbapisecret=None, 
		latitude=None, 
		longitude=None,
		local_ip=None
	):
		self.apitoken = apitoken
		self.ngroktoken = ngroktoken
		self.subdomain = subdomain
		self.dynamicimages = dynamicimages
		self.secret = secret
		self.cbapikey = cbapikey
		self.cbapisecret = cbapisecret
		self.latitude = latitude
		self.longitude = longitude
		self.local_ip = local_ip

	def initialize(self, ip):
		# generate a new API token
		self.apitoken = generate_token()

		# remainder of settings
		self.ngroktoken = ""
		self.subdomain = ""
		self.dynamicimages = 1
		self.secret = generate_token(size=8, caselimit=True) # not used, but fun
		self.cbapikey = ""
		self.cbapisecret = ""
		self.cbaccesstoken = ""
		self.cbrefreshtoken = ""

		# get geodata
		geo_data = get_geodata()
		self.latitude = geo_data['latitude']
		self.longitude = geo_data['longitude']

		# set local IP address
		self.local_ip = ip

		# create entry
		self.update(self)

	def token_refresh(self):
		self.apitoken = generate_token(size=64)

	def build_tunnel_conf(self):
		# move file to backup
		tunnel_conf_file = '%s/%s' % (app.config['BASE_PATH'], app.config['POOL_TUNNEL_CONF'])

		# create yaml object and write to file
		# only do this if all user entered values are ready to role
		if self.cbapikey and self.cbapisecret and self.ngroktoken:
			# set development port if we are in debug mode
			if app.config['DEBUG']:
				port = 5000
			else:
				port = 80

			# create data structure for yaml file
			data = dict(
				auth_token = self.ngroktoken.encode('ascii','ignore'),
				tunnels = dict(
					xoviova = dict(
						subdomain = self.subdomain.encode('ascii', 'ignore'),
						proto = dict(
							https = port
						)
					)
				)
			)
			# write the yaml file out
			with open(tunnel_conf_file, 'w') as yaml_file:
				yaml_file.write( yaml.dump(data, default_flow_style=False))


# settings check model
class Status(CRUDMixin, db.Model):
	__tablename__ = 'status'
	id = db.Column(db.Integer, primary_key=True)
	updated = db.Column(db.Integer)
	openstack_check = db.Column(db.Integer)
	coinbase_check = db.Column(db.Integer)
	ngrok_check = db.Column(db.Integer)
	flavors_check = db.Column(db.Integer)
	images_check = db.Column(db.Integer)
	token_check = db.Column(db.Integer)

	# check settings for setup warning indicators
	def check_settings(self):
		status = db.session.query(Status).first()
		
		# calculate cache timeout (120 seconds)
		epoch_time = int(time.time())
		try:
			if (status.updated + 900) < epoch_time:
				# it's been 15 minutes so we are hot
				check = True
			else:
				check = False
		except:
			# need to create a new entry
			check = True
			status = Status()

		# objects
		appliance = Appliance().get()
		openstack = OpenStack()
		flavors = Flavors()

		# if the cache time has been a while, or we are on
		# the configuration page, check settings and cache
		if check:
			# openstack connected?
			openstack_check = openstack.check()
			status.openstack_check = openstack_check

			# coinbase tokens working?
			coinbase_check = coinbase_checker(appliance)
			status.coinbase_check = coinbase_check

			# token valid?
			response = pool_api_connect('authorization', appliance.apitoken)
			if response['response'] == "success":
				token_check = True
			else:
				token_check = False
			status.token_check = token_check

			# update database
			status.updated = epoch_time

			# ngrok connection
			ngrok_check = ngrok_checker(appliance)
			status.ngrok_check = ngrok_check
			
			# one flavor installed?
			flavors_check = flavors.check()
			status.flavors_check = flavors_check

			# images aren't really checked
			status.images_check = True

			status.update()
		
		else:
			# stuff we check all the time
			# openstack connected?
			openstack_check = openstack.check()
			status.openstack_check = openstack_check

			# ngrok connection
			ngrok_check = ngrok_checker(appliance)
			status.ngrok_check = ngrok_check

			# one flavor installed?
			flavors_check = flavors.check()
			status.flavors_check = flavors_check

			# images good?
			status.images_check = True

			# update
			status.update()

		# build the response object
		settings = {
			"flavors": status.flavors_check,
			"images": 1, 
			"openstack": status.openstack_check,
			"coinbase": status.coinbase_check,
			"ngrok": status.ngrok_check,
			"token": status.token_check,
		}
			
		return settings

	# delete all settings
	def flush(self):
		status = db.session.query(Status).first()
		if status:
			status.delete()
		db.session.commit()
