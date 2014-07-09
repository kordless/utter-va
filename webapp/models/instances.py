import time

from HTMLParser import HTMLParser
from IPy import IP

from webapp import app
from webapp import db

from webapp.models.mixins import CRUDMixin

from webapp.libs.utils import generate_token, row2dict
from webapp.libs.pool import pool_instance

from webapp.models.models import Appliance
from webapp.models.addresses import Addresses
from webapp.models.images import Images
from webapp.models.flavors import Flavors

# instance model
class Instances(CRUDMixin, db.Model):
	__tablename__ = 'instances'
	id = db.Column(db.Integer, primary_key=True)
	created = db.Column(db.Integer)
	updated = db.Column(db.Integer) 
	expires = db.Column(db.Integer)
	name = db.Column(db.String(100))
	osid = db.Column(db.String(100))
	privateipv4 = db.Column(db.String(100))
	publicipv4 = db.Column(db.String(100))
	publicipv6 = db.Column(db.String(100))
	console = db.Column(db.String(8192))
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
	
	callback_url = db.Column(db.String(1024))
	dynamic_image_url = db.Column(db.String(1024))
	post_creation = db.Column(db.String(8192))

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
		privateipv4=None,
		publicipv4=None,
		publicipv6=None,
		console=None,
		ssltunnel=None,
		state=None,
		callback_url=None,
		dynamic_image_url=None,
		post_creation=None,
		flavor_id=None,
		image_id=None,
		address_id=None
	):
		self.created = created
		self.updated = updated
		self.expires = expires
		self.name = name
		self.osid = osid
		self.privateipv4 = privateipv4
		self.publicipv4 = publicipv4
		self.publicipv6 = publicipv6
		self.console = console
		self.ssltunnel = ssltunnel
		self.state = state
		self.callback_url = callback_url
		self.dynamic_image_url = dynamic_image_url
		self.post_creation = post_creation
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
			app.logger.info("Instance %s toggled to %s" % (instance.name, active))

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
			app.logger.info("Created new instance=(%s)." % instance.name)

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

		# get instance console output - only run if we've got an osid
		# basically this only runs when we get a repayment
		if self.osid:
			from webapp.libs.openstack import instance_console
			response = instance_console(self)
			if 'console' in response['result']:
				self.console = response['result']['console']

		# update the instance
		self.update()

		# make a call to the callback url to report instance details
		# this will call the pool on initial payment.  subsequent payment calls go to 
		# whatever callback address is set in the start() method below.
		appliance = Appliance().get()
		callback_url = self.callback_url
		
		pool_response = pool_instance(url=callback_url, instance=self, appliance=appliance)

		if pool_response['response'] == "success":	
			# response
			response['result']['message'] = "Added %s seconds to %s's expire time." % (purchased_seconds, self.name)
			response['result']['instance'] = row2dict(self)
		else:
			app.logger.error("Error sending instance=(%s) data to pool." % self.name)

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

		# load the callback url (expected to be None)
		callback_url = self.callback_url
		
		# check if instance needs to reset
		epoch_time = int(time.time())
		if self.expires < epoch_time:
			# instance time expired, so don't start
			self.state = 1
			self.update()
			response['response'] = "fail"
			response['result']['message'] = "Instance payment is expired.  Now waiting on payment."

		# we run a maximum of 7 callback checks
		for loop_count in range(7):
			# make a call to the callback url to get instance details
			pool_response = pool_instance(url=callback_url, instance=self, appliance=appliance)

			# check for a failure to contact the callback server
			if pool_response['response'] == "fail":
				response['result']['message'] = pool_response['result']
				# probably should call the pool up and tell them...
				return response

			# look and see if we have a callback_url in the response
			try:
				callback_url = pool_response['result']['instance']['callback_url']
				# run the loop again to call the callback url
				continue 
			except:
				# break out
				break
		
		# for else returns a depth error
		else:
			response['response'] = "fail"
			response['result']['message'] = "Callback depth exceeded."
			return response
		
		# and lo, callback_url is saved
		self.callback_url = callback_url
		self.update()

		# get the image name if it exists in the response 
		try:
			image_name = pool_response['result']['instance']['image']
			image = db.session.query(Images).filter_by(name=image_name).first()
			self.image_id = image.id
			self.update()
		except:
			image_name = None
			# get the dynamic image url if it exists in the response
			try:
				dynamic_image_url = pool_response['result']['instance']['dynamic_image_url']
				self.dynamic_image_url = dynamic_image_url
				self.update()
			except:
				# not good, but we can use a default
				image = db.session.query(Images).first()
				self.image_id = image.id
				self.update()

		# post creation file is blank to start
		post_creation_ssh_key_combo = ""
		
		# load the parser to unencode jinja2 template escaping from appliance
		h = HTMLParser()

		# ssh_key unrolling
		try:
			ssh_key = pool_response['result']['instance']['ssh_key'] # an array

			# loop through both strings and cat onto post_creation_ssh_key_combo
			# using prefered method of injecting keys with cloud-init
			post_creation_ssh_key_combo += "#cloud-config\n"
			post_creation_ssh_key_combo += "ssh_authorized_keys:\n"
			for line in ssh_key:
				post_creation_ssh_key_combo += " - %s\n" % h.unescape(line)
			post_creation_ssh_key_combo += "\n"

		except:
			# do nothing on various key failure
			pass

		# post creation configuration handling
		try:
			post_creation = pool_response['result']['instance']['post_creation'] # an array

			for line in post_creation:
				# import what the user put in the textbox for their wisp
				post_creation_ssh_key_combo += "%s\n" % h.unescape(line)

		except:
			# do nothing on post creation failure
			pass

		# update the instance with post creation
		self.post_creation = post_creation_ssh_key_combo
		self.update()

		# deal with creating dynamic image or use predefined one
		if self.dynamic_image_url:
			image = Images().get_or_create_by_instance(self)
		else:
			image = Images().get_by_id(self.image.id)

		if not image:
			response['response'] = "fail"
			response['result']['message'] = "Failed to create dynamic image."
			return response
		else:
			self.image = image
			self.update()

		# take the image and verify install
		osimage = image_verify_install(self.image)

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

		# tell openstack to start the instance
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

		return response

	# returns information about an instance once it moves to ACTIVE state
	# sets information about the instance and does a callback with info
	def nudge(self):
		from webapp.libs.openstack import instance_info
		from webapp.libs.openstack import instance_console

		# get instance console output
		response = instance_console(self)
		if 'console' in response['result']:
			self.console = response['result']['console']
		self.update()

		# get instance (server) info
		response = instance_info(self)

		# set start state
		start_state = self.state

		# set instance meta data
		if response['response'] == "success":
			server = response['result']['server']

			# if the state is ACTIVE, we set to be running state==4
			if server.status == "ACTIVE":
				# set network info
				self.state = 4

				# extract IP addresses using IPy
				# in some circumstances this will squash multiple same/same address types
				# we only extract and store one each of private ipv4, public ipv4, and public ipv6
				for key in server.networks.keys(): # any network names
					for address in server.networks[key]: # loop through each address for each network
						# private IPv4
						if IP(address).iptype() == "PRIVATE" and IP(address).version() == 4:
							self.privateipv4 = address
						# public IPv4
						elif IP(address).iptype() == "PUBLIC" and IP(address).version() == 4:
							self.publicipv4 = address
						# public IPv6
						elif IP(address).iptype() == "ALLOCATED ARIN" and IP(address).version() == 6:
							self.publicipv6 = address

				# update the instance
				self.update()
			
			elif server.status == "ERROR":
				# instance failed to start
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

		# make a call to the callback url to report instance details on state change
		if self.state != start_state:
			appliance = Appliance().get()
			callback_url = self.callback_url
			pool_response = pool_instance(url=callback_url, instance=self, appliance=appliance)

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
		from webapp.libs.openstack import instance_console

		# build the response
		response = {"response": "success", "result": {"message": "", "server": {}}}

		# get instance (server) info
		cluster_response = instance_info(self)
		server = cluster_response['result']['server']

		# we all have limited time in this reality
		epoch_time = int(time.time())

		# set start state
		start_state = self.state

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
					app.logger.error("OpenStack says instance=(%s) isn't in the correct state.  Setting to restart." % self.name)
				else:
					# expired but in a weird state - destroy
					response = instance_decommission(self)
					response['result']['message'] = "Instance %s decommissioned." % self.name
					self.state = 7
		else:
			# openstack can't find this instance
			if self.expires > epoch_time:
				# set instance to restart - not expired, should be running
				response['response'] = "fail" # technically, someone is probably fucking with things
				response['result']['message'] = "Setting instance %s to restart." % self.name
				self.state = 2 # will be started shortly after this by start
				app.logger.error("OpenStack doesn't know about instance=(%s). Setting to restart." % self.name)
			else:
				# no reason to be running
				response['response'] = "fail"
				response['result']['message'] = "Instance %s decommissioned." % self.name
				self.state = 7 # will be deleted shortly after this by trashman

		# get instance console output
		cluster_response = instance_console(self)
		if 'console' in response['result']:
			self.console = response['result']['console']

		# update
		self.update()

		# make a call to the callback url to report instance details on state change
		if self.state != start_state:			
			appliance = Appliance().get()
			callback_url = self.callback_url
			pool_response = pool_instance(url=callback_url, instance=self, appliance=appliance)

		return response

	# delete and cleanup instances which have been decomissioned
	def trashman(self):
		from webapp.libs.openstack import instance_info
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

		# make a call to the callback url to report instance details
		appliance = Appliance().get()
		callback_url = self.callback_url
		pool_response = pool_instance(url=callback_url, instance=self, appliance=appliance)

		return response

	def __repr__(self):
		return '<Instance %r>' % (self.name)
