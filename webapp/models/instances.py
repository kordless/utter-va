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

from utter_libs.schemas.model_mixin import ModelSchemaMixin
from utter_libs.schemas import schemas

# instance model
class Instances(CRUDMixin, db.Model, ModelSchemaMixin):
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
	image_id = db.Column(db.Integer, db.ForeignKey('images.id'))
	post_creation = db.Column(db.String(8192))
	message = db.Column(db.String(400))
	message_count = db.Column(db.Integer)

	# foreign keys
	flavor_id = db.Column(db.Integer, db.ForeignKey('flavors.id'))

	# relationships
	flavor = db.relationship('Flavors', foreign_keys='Instances.flavor_id')

	# which schema should be used for validation and serialization
	object_schema = schemas['InstanceSchema']

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
		image_url=None,
		post_creation=None,
		message=None,
		message_count=0,
		flavor_id=None,
		image_id=None,
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
		self.image_url = image_url
		self.post_creation = post_creation
		self.message = message
		self.message_count = message_count
		self.flavor_id = flavor_id
		self.image_id = image_id

	@property
	def appliance(self):
		return Appliance.get()

	# generate a list of private addresses with describing properties. this format
	# is compatible with the schema that's being sent to the pool. actually i
	# optimally the local schema would store IPs in a similar format as the one
	# that's being generated here, but that can still be done later, so for now 
	# i just add this method to "translate" and make everything compatible.
	@property
	def ip_addresses(self):
		return [
			{
				'version': addr['version'],
				'scope': addr['scope'],
				'address': addr['address'],
			} for addr in [
				{
					'version': 4,
					'scope': 'public',
					'address': self.publicipv4,
				}, {
					'version': 4,
					'scope': 'private',
					'address': self.privateipv4,
				}, {
					'version': 6,
					'scope': 'public',
					'address': self.publicipv6,
				}]
			if addr['address'] != None
		]

	# generate a list of lines of console output. can be used as property to
	# be 1:1 mapped to the instance api schema
	@property
	def console_output(self):
		from webapp.libs.openstack import instance_console
		response = instance_console(self)
		if response['response'] == "error":
			raise Exception("Failed to get console_output.")
		if response['response'] == "success":
			return response['result']['console']
		return []

	# property that returns the associated address model
	@property
	def address_model(self):
		address = db.session.query(Addresses).join(
			Instances,
			Instances.id == Addresses.instance_id).filter(
				Instances.id == self.id).first()
		return address

	# get the address string of this instance by joining with address table, also used
	# as 1:1 mapping with instance api schema
	@property
	def address(self):
		address = self.address_model
		if address:
			return address.address
		return ""

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

	# instance reservations
	def reserve(self, callback_url, flavor_id):
		# build response
		response = {"response": "success", "result": {"message": ""}}

		# find a willing instance
		instance = db.session.query(Instances).filter_by(state=1, flavor_id=flavor_id).first()

		if instance:
			# set that instance to reserved (active == 10)
			instance.state = 10
			instance.callback_url = callback_url
			instance.update()

			# tell the pool we're using it (url must be empty string to tell pool)
			appliance = Appliance().get()
			pool_response = pool_instance(url="", instance=self, appliance=appliance)
			
			# response
			response['result']['message'] = "Instance %s marked as reserved." % instance.name
			response['result']['instance'] = row2dict(instance)
			response['result']['ask'] = instance.flavor.ask
			response['result']['address'] = instance.address.address
		else:
			response['response'] = "error"
			response['result']['message'] = "No available instances."
		
		return response

	# whip up a nice instance for receiving payments
	def mix(self, flavor):
		# build response
		response = {"response": "success", "result": {"message": ""}}

		# the first instance which has this flavor assigned but is not running (active == 1)
		instances = db.session.query(Instances).filter_by(flavor_id=flavor.id, state=1).all()

		# create a minimum number of instances based on hot amount for flavor
		if len(instances) < flavor.hot:
			for x in range(len(instances), flavor.hot):		
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
				address = addresses.assign(instance.id)
				if not address:
					# we have no address, so delete what we made
					instance.delete(instance)

			response['result']['message'] = "Created new instance and assigned address."
			app.logger.info("Created new instance=(%s)." % instance.name)

		else:
			# found enough instances - make sure they have addresses assigned to them
			for instance in instances:
				Addresses().assign(instance.id)
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

		# if we're not running (state==1 or 10), set the run state to light (to be started)
		# if we're suspended (state==5), set the run state to relight (to be unsuspended)
		# cron jobs will take care of the rest of the job of starting/unsuspending
		# NOTE: We're getting paid pennies for doing nothing until cronjob runs!
		if self.state == 1 or self.state == 10: 
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
		callback_url = self.callback_url
		appliance = Appliance().get()
		
		pool_response = pool_instance(url=callback_url, instance=self, appliance=appliance)

		if pool_response['response'] == "success":	
			# overload response
			response['result']['message'] = "Added %s seconds to %s's expire time." % (purchased_seconds, self.name)
			response['result']['instance'] = row2dict(self)
		else:
			# note the error in the instance object
			self.message_count = self.message_count + 1
			self.message = pool_response['result']['message']
			self.update()

			# load response and log
			response = pool_response
			app.logger.error("Error sending instance=(%s) data to pool." % self.name)

		return response

	# move instances from light to warm
	def start(self):
		from webapp.libs.openstack import flavor_verify_install
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
			response['response'] = "error"
			response['result']['message'] = "Instance payment is expired.  Now waiting on payment."

		# we run a maximum of 7 callback checks
		for loop_count in range(7):
			# make a call to the callback url to get instance details
			next_state = 3 # hack the expected next state into the pool packet
			pool_response = pool_instance(url=callback_url, instance=self, next_state=next_state, appliance=appliance)

			# check for a failure to contact the callback server
			if pool_response['response'] == "error":
				self.message = pool_response['result']['message']
				self.message_count = self.message_count + 1
				self.update()
				return pool_response

			# look and see if we have a callback_url in the response
			try:
				callback_url = pool_response['result']['instance']['callback_url']
				# run the loop again to call the callback url
				if callback_url == '':
					break
			except:
				break
		else:
			response['response'] = "error"
			response['result']['message'] = "Callback depth exceeded."
			self.message = response['result']['message']
			self.message_count = self.message_count + 1
			self.update()
			return response

		# get dictionary from pool's reply
		start_params = schemas['InstanceStartParametersSchema'](
			**pool_response['result']['instance']).as_dict()

		# and lo, callback_url is saved
		self.callback_url = start_params['callback_url']

		# lookup the image for this instance, or create it otherwise
		image = Images.query.filter_by(url=start_params['image_url']).first()
		if not image:
			image = Images(url=start_params['image_url'],
										 name=start_params['image_name'])
			try:
				image.save()
			except Exception as e:
				app.logger.error("Error creating flavor on OpenStack: \"{0}\"".format(str(e)))
				response['response'] = "error"
				response['result']['message'] = "Error creating image."
				return response
		self.image = image
		self.update()

		# post creation file is blank to start
		post_creation_ssh_key_combo = ""
		
		# load the parser to unencode jinja2 template escaping from appliance
		h = HTMLParser()

		# ssh_key unrolling
		try:
			# loop through both strings and cat onto post_creation_ssh_key_combo
			# using prefered method of injecting keys with cloud-init
			post_creation_ssh_key_combo += "#cloud-config\n"
			post_creation_ssh_key_combo += "ssh_authorized_keys:\n"
			for line in start_params['ssh_keys']:
				post_creation_ssh_key_combo += " - %s\n" % h.unescape(line)
			post_creation_ssh_key_combo += "\n"

		except:
			# do nothing on various key failure
			pass

		# post creation configuration handling
		try:

			for line in start_params['post_create']:
				# import what the user put in the textbox for their wisp
				post_creation_ssh_key_combo += "%s\n" % h.unescape(line)

		except:
			# do nothing on post creation failure
			pass

		# update the instance with post creation
		self.post_creation = post_creation_ssh_key_combo
		self.update()

		# take the instance's flavor and verify install
		flavor = Flavors().get_by_id(self.flavor.id)
		flavor_response = flavor_verify_install(flavor)

		if flavor_response['response'] == "error" or flavor_response['response'] == "forbidden":
			# we've failed to install flavor, so we disable it
			flavor.osid = ""
			flavor.active = 0
			flavor.update()

			# now we disable the other instances using the flavor
			instances = Instances()
			instances.toggle(flavor.id, 0)

			# disable this instance
			self.state = 0
			self.expires = self.created # zeros out the payment
			self.update()

			if flavor_response['response'] == "forbidden":
				response['result']['message'] = \
					"Not allowed to create flavor inside OpenStack, disabling flavor creation"

				# log it
				app.logger.error("Disabling all instances using flavor=(%s) and disabling "
												 "creation of flavors due to lack of permissions." % flavor.name)

			else:
				# log it
				app.logger.error("Disabling all instances using flavor=(%s) due to "
												 "OpenStack failure." % flavor.name)

				# build the response and return
				response['result']['message'] = flavor_response['result']['message']

			response['response'] = "error"
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
		from webapp.libs.openstack import try_associate_floating_ip
		from webapp.libs.openstack import instance_info
		from webapp.libs.openstack import instance_console
		from webapp.libs.openstack import instance_decommission

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

				# try to get a floating ip for the new server
				float_response = try_associate_floating_ip(server)

				# check if call got a floating IP
				if float_response['response'] == "success":
						# get instance info again to pick up new IP
						response = instance_info(self)

						# load the response into the server object
						if response['response'] == "success":
							server = response['result']['server']

				else:
					# log 'errors' in floating assignment
					app.logger.info(float_response['result']['message'])

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

			# ERROR status from openstack
			elif server.status == "ERROR":
				# instance failed to start, so delete and reset to paid
				response = instance_decommission(self)

				self.state = 2 # will be started again shortly
				self.update()

				response['response'] = "error"
				response['result']['message'] = "OpenStack errored on instance start."
				
				app.logger.error("OpenStack error on starting instance=(%s).  Setting to restart." % self.name)

			# SPAWNING status from openstack
			else:
				# we all have limited time in this reality
				epoch_time = int(time.time())			

				# wait_timer is 5 minutes after the last update
				wait_timer = self.updated + 300

				# test to see if we are 'hung' on SPAWNING for more than wait_timer
				if epoch_time > wait_timer:
					# we're now  past when the instance needed to move to RUNNING
					response = instance_decommission(self)

					response['response'] = "error"
					response['result']['message'] = "Setting instance %s to restart." % self.name
					
					self.state = 2 # will be started shortly after this by start
					self.updated = epoch_time # given we 'timed' out, give the instance more time
					self.update()

					"""
					of anyplace, this is where you *might* want to add some time to the instance
					because a time based payment has been made on it.  however, this could lead to 
					a situation where an instance gets stuck in a circular state of erroring, getting
					more time, erroring again, rinse and repeat.  instead of embracing this eventuality, 
					we choose to short the customer her measly few cents instead, and let it serve as a 
					as an excuse to add 'karma hits' on bad starts from providers as a feature later
					"""

					app.logger.error("OpenStack hung starting instance=(%s).  Setting to restart." % self.name)
					
				else:
					# this is a 'soft' fail
					response['response'] = "error"
					response['result']['message'] = "Still starting instance=(%s)." % self.name


		# OpenStack reports instance NOT FOUND	
		else:
			# we all have limited time in this reality
			epoch_time = int(time.time())			

			# we first check if we're outright expired (shouldn't happen)
			if self.expires < epoch_time:
				# no reason to be running as we're expired
				self.state = 7 # will be deleted shortly after this by trashman
				self.update()

				response['response'] = "error"
				response['result']['message'] = "Instance %s decommissioned." % self.name

				app.logger.error("OpenStack couldn't find expired instance=(%s). Decomissioning." % self.name)

			else:
				# we didn't find the instance in openstack, yet we should be running
				self.state = 2 # set to be started again
				self.update()

				response['response'] = "error"
				response['result']['message'] = "OpenStack couldn't find instance.  Restarting."
				
				app.logger.error("OpenStack couldn't find instance=(%s). Setting to restart." % self.name)

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
				if self.state == 2:
					# check error rate
					if self.message_count > 10:
						# we're failing to start the instance, so decomission
						response['result']['message'] = "Instance %s decommissioned." % self.name
						self.state = 7
						app.logger.error("Exceeded error rate on callbacks for instance=(%s). Decomissioning." % self.name)
				else:
					# set instance to restart - not expired, should be running
					response['response'] = "error" # technically, someone is probably fucking with things
					response['result']['message'] = "Setting instance %s to restart." % self.name
					self.state = 2 # will be started shortly after this by start
					app.logger.error("OpenStack doesn't know about instance=(%s). Setting to restart." % self.name)
			else:
				# no reason to be running
				response['response'] = "error"
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
			self.address_model.release()
			self.delete(self)
			response['result']['message'] = "Instance %s has been deleted." % self.name

		# make a call to the callback url to report instance details
		appliance = Appliance().get()
		callback_url = self.callback_url
		pool_response = pool_instance(url=callback_url, instance=self, appliance=appliance)

		return response

	def __repr__(self):
		return '<Instance %r>' % (self.name)
