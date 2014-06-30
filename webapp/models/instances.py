import time

from webapp import app
from webapp import db

from webapp.models.mixins import CRUDMixin

from webapp.libs.utils import generate_token, row2dict
from webapp.models.models import Appliance
from webapp.models.addresses import Addresses

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
		response = {"response": "success", "result": {"message": ""}}

		# the first instance which has this flavor assigned but is not running (active == 1)
		instances = db.session.query(Instances).filter_by(flavor_id=flavor.id, state=1).all()

		# create a minimum number of instances based on hot amount for flavor
		if len(instances) < flavor.hot:
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
			# found enough instances - make sure they have addresses assigned to them
			for instance in instances:
				instance.address = Addresses().assign(instance.id)
				instance.update()

			response['result']['message'] = "Found existing instances and assigned addresses."

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
			self.updated = epoch_time
		elif self.state == 5:
			self.state = 6
			self.expires = epoch_time + purchased_seconds # starting from now
			self.updated = epoch_time
		else:
			# states 0, 2, 3, 4, 6, 7
			self.expires = self.expires + purchased_seconds # starting from expire time
			self.updated = epoch_time

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
		response = {"response": "success", "result": {"message": ""}}

		# appliance
		appliance = Appliance().get()

		# make a call to the pool with the instance details
		pool_response = pool_instance(instance=self, appliance=appliance)
		print pool_response

		if pool_response['response'] == "fail":
			response['result']['message'] = pool_response['result']
			return response

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
				print server.addresses
				for address in server.addresses['private']:
					if address['version'] == 4:
						self.privateipv4 = address['addr']
					if address['version'] == 6:
						self.publicipv6 = address['addr']
				self.update()
			elif server.status == "ERROR":
				# instance failed to start
				print "error"
				response['response'] = "fail"
				response['message'] = "Server isn't in active state yet."
			else:
				response['response'] = "fail"
				response['message'] = "Server isn't in a known state."

		# openstack can't find this instance	
		else:
			# we all have limited time in this reality
			epoch_time = int(time.time())			
			
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

			# notify the pool server of update
			updated = False
			if updated:
				pass

		return response

	# HOUSEKEEPING WORKS ON STATE==4, STATE==5 and STATE==6 INSTANCES ONLY
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
		# print server.status
		# print epoch_time
		# print self.expires

		# this is complicated...because we aren't EC with OpenStack...or I'm crazy
		if cluster_response['response'] == "success": 
			# openstack responded it found this instance
			if server.status == "ACTIVE":
				# openstack says the server is running
				if self.expires < epoch_time:
					# suspend the instance for non-payment
					response = instance_suspend(self)
					response['result']['message'] = "Instance %s suspended." % self.name
					self.state = 5
				elif self.expires > epoch_time:
					# openstack says we're running, and we're paid
					if self.state == 5 or self.state == 6:
						# we move the instance to starting mode
						response['result']['message'] = "Instance %s is starting." % self.name
						self.state = 3
			elif server.status == "SUSPENDED":
				# openstack says this instance is suspended
				if self.expires > epoch_time:
					# should be running because not expired
					response = instance_resume(self)
					response['result']['message'] = "Instance %s resumed." % self.name
					self.state = 3 # mark as starting
				if self.expires + app.config['POOL_DECOMMISSION_TIME'] < epoch_time:
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
					# expired but in a weird state - destroy
					response = instance_decommission(self)
					response['result']['message'] = "Instance %s decommissioned." % self.name
					self.state = 7
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
			response['result']['message'] = "Terminating instance %s" % self.name
		else:
			# delete this instance into forever
			address = Addresses().get_by_id(self.address_id)
			address.release()
			self.delete(self)
			response['result']['message'] = "Instance %s has been deleted." % self.name

		return response

	def __repr__(self):
		return '<Instance %r>' % (self.name)
