import os
import yaml
import shutil
import json
import time

from urlparse import urlparse

from keystoneclient.v2_0 import client as keyclient
from flask.ext.login import UserMixin
from werkzeug import generate_password_hash, check_password_hash

from webapp import app
from webapp import db, bcrypt

from webapp.models.mixins import CRUDMixin
from webapp.libs.utils import server_connect, coinbase_generate_address, coinbase_get_addresses
from webapp.libs.utils import generate_token, row2dict
from webapp.libs.utils import uninstall_image
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
	instanceid = db.Column(db.Integer)
	subdomain = db.Column(db.String(100))

	def __init__(self,
		address=None,
		token=None,
		instanceid=None,
		subdomain=None
	):
		self.address = address
		self.token = token
		self.instanceid = instanceid
		self.subdomain = subdomain

	def __repr__(self):
		return '<Address %r>' % (self.address)
	
	def sync(self, appliance):
		# grab image list from pool server
		response = coinbase_get_addresses(appliance=appliance)

		if response['response'] == "success":
			remoteaddresses = response['result']['addresses']

			# update database for with remote addresses
			for remoteaddress_address in remoteaddresses:
				# work around coinbase's strange address:address thing
				remoteaddress = remoteaddress_address['address']

				# see if we have a matching image
				address = db.session.query(Addresses).filter_by(address=remoteaddress['address']).first()
				
				# we don't have the address at coinbase in database
				if address is None:
					# create a new image
					address = Addresses()
					address.address = remoteaddress['address']
					address.token = remoteaddress['label']
					address.instanceid = 0 # no instances yet
					address.subdomain = urlparse(remoteaddress['callback_url']).hostname.split('.')[0]

					# add and commit
					address.update(address)

				# we have the address already and need to update it
				else:
					# update address from remote images
					address.address = remoteaddress['address']
					address.token = remoteaddress['label']
					address.subdomain = urlparse(remoteaddress['callback_url']).hostname.split('.')[0]

					# add and commit
					address.update(address)

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
	def assign(self, appliance, instanceid):
		# check if the instance id is already assigned to an address (just in case)
		address = db.session.query(Addresses).filter_by(instanceid=instanceid).first()
		
		# if we found an address, just return it
		if address:
			response = {"response": "success", "result": {}}
			response['result']['address'] = row2dict(address)
			return address
		else:
			# check if we have an empty address to assign
			address = db.session.query(Addresses).filter_by(instanceid=0).first()		
			
			# we found one, so assign instanceid, appliance subdomain
			if address:
				# assign the instance id to the address
				address.instanceid = instanceid
				# leave the subdomain alone from the sync below
				# address.subdomain
				address.update(address)
				
				response = {"response": "success", "result": {}}
				response['result']['address'] = row2dict(address)
				return address
			else:
				# ask coinbase for new address and set callback
				# NOTE: label == token
				label = generate_token(size=16, caselimit=True)
				callback_url = "https://%s.%s.com/api/address/%s" % (
					appliance.subdomain, 
					app.config['POOL_SSL_PROXY_DOMAIN'], 
					label
				)
				response = coinbase_generate_address(appliance, callback_url, label)

				# create new address in db
				if response['response'] == "success":
					address = Addresses()
					address.address = response['result']['address']
					address.token = response['result']['label']
					address.subdomain = appliance.subdomain
					address.update()

					# return our version of the overloaded response
					response = {"response": "success", "result": {}}
					response['result']['address'] = row2dict(address)
					return address
				else:
					# something went wrong with coinbase, so lift the response
					return response


	# release a bitcoin address back into pool
	def release(self, instanceid):
		# get the address assigned to the instance
		address = db.session.query(Addresses).filter_by(instanceid=instanceid).first()
		
		if address:
			# now change the instanceid to indicate it's available
			address.instanceid = 0
			address.update(address)
			response = {"response": "success", "result": ""}
			response['result']['address'] = row2dict(address)
			return address
		else:
			# found nothing so return fail response
			response = {"response": "fail", "result": "no address is managing instance %s" % instanceid}
			return response


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
	flavor = db.Column(db.Integer)
	image = db.Column(db.Integer)
	privateipv4 = db.Column(db.String(100))
	publicipv4 = db.Column(db.String(100))
	publicipv6 = db.Column(db.String(100))
	ssltunnel = db.Column(db.String(400))

	state = db.Column(db.Integer) 
	# instance state is one of:
	# 0 - inactive
	# 1 - payment address available (warm)
	# 2 - payment observed from callback (start)
	# 3 - instance running (hot)
	# 4 - instance halted (cooldown)
	# 5 - instance decommissioned (removed)
	
	sshkey = db.Column(db.String(2048))
	callback_url = db.Column(db.String(1024))

	def __init__(self, 
		created=None,
		updated=None,
		expires=None,
		name=None,
		osid=None,
		poolid=None,
		flavor=None,
		image=None,
		privateipv4=None,
		publicipv4=None,
		publicipv6=None,
		ssltunnel=None,
		state=None,
		sshkey=None,
		callback_url,
	):
		self.created = created
		self.updated = updated
		self.expires = expires
		self.name = name
		self.osid = osid
		self.poolid = poolid
		self.flavor = flavor
		self.image = image
		self.privateipv4 = privateipv4
		self.publicipv4 = publicipv4
		self.publicipv6 = publicipv6
		self.ssltunnel = ssltunnel
		self.state = state
		self.sshkey = sshkey
		self.callback_url = callback_url

	def get_by_token(self, token):
		instance = db.session.query(Instances).filter_by(token=token).first()
		return instance
	
	def sync(self, appliance):
		# create instances for flavors
		# get a list of the current flavors appliance is serving
		flavors = db.session.query(Flavors).filter_by(active=1).all()

		# run through flavors and make sure we have an open instance for them
		for flavor in flavors:
			# the first instance which has this flavor assigned but is not running (active == 1)
			instance = db.session.query(Instances).filter_by(flavor=flavor.id, state=1).first()

			# startable instance NOT available for this flavor, so create a warm one
			if not instance:
				# create a new instance		
				instance = Instances()
				instance.name = "smi-%s" % generate_token(size=8, caselimit=True)
				instance.flavor = flavor.id

				# grab the first available image for a holder for the warm instance
				image = db.session.query(Images).first()
				instance.image = image.id

				# timestamps
				epoch_time = int(time.time())
				instance.created = epoch_time
				instance.updated = epoch_time
				instance.expires = epoch_time # already expired

				# set state
				instance.state = 1 # has address, but no payments/not started (warm)

				# update
				instance.update()

				# assign addresses
				addresses = Addresses()
				aresponse = addresses.assign(appliance, instance.id)
				print aresponse

		# overload the results with the list of current flavors
		response = {"response": "success", "result": {}}
		response['result']['instances'] = []
		instances = db.session.query(Instances).all()

		for instance in instances:
			response['result']['instances'].append(row2dict(instance))

		return response

	def __repr__(self):
		return '<Instance %r>' % (self.name)


# images model
class Images(CRUDMixin,  db.Model):
	__tablename__ = 'images'
	id = db.Column(db.Integer, primary_key=True)
	osid = db.Column(db.String(100))
	name = db.Column(db.String(100), unique=True)
	description = db.Column(db.String(200))
	url = db.Column(db.String(400), unique=True)
	diskformat = db.Column(db.String(100))
	containerformat = db.Column(db.String(100))
	size = db.Column(db.Integer)

	# 8 - uninstall
	flags = db.Column(db.Integer)

	# 0 - not installed, 1 - know about it, 2 - installing, 3 - installed
	active = db.Column(db.Integer)

	def __init__(
		self, 
		osid=None, 
		name=None, 
		description=None, 
		url=None, 
		size=None, 
		diskformat=None, 
		containerformat=None, 
		flags=None
	):
		self.osid = osid
		self.name = name
		self.description = description
		self.url = url
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
		response = server_connect(method="images", apitoken=appliance.apitoken)

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

				# we have the image and need to update it
				else:
					# update image from remote images
					image.name = remoteimage['name']
					image.description = remoteimage['description']
					image.url = remoteimage['url']
					image.diskformat = remoteimage['diskformat']
					image.containerformat = remoteimage['containerformat']
					image.flags = remoteimage['flags']
					
					# udpate
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
		response = server_connect(method="flavors", apitoken=appliance.apitoken)

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
class OpenStack(CRUDMixin,  db.Model):
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
					auth_url = openstack.authurl
				)
			except:
				return False
		else:
			return False
		
		return True


# appliance model
class Appliance(CRUDMixin,  db.Model):
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
		self.subdomain = generate_token(size=16, caselimit=True)
		self.dynamicimages = 1
		self.secret = generate_token(size=8, caselimit=True)
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

		try:
			with open(tunnel_conf_file):
				tmpext = generate_token(size=6)
				shutil.move(tunnel_conf_file, "%s.%s" % (tunnel_conf_file, tmpext))
		except IOError:
			pass

		# create yaml object and write to file
		# only do this if all user entered values are ready to role
		if self.cbapikey and self.cbapisecret and self.ngroktoken:
			# set development port if we are in debug mode
			if app.config['DEBUG']:
				port = 5000
			else:
				port = 80

			# need to loop through subdomains we found from coinbase
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
