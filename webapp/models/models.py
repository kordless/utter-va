import yaml
import time

from keystoneclient.v2_0 import client as keyclient
from flask.ext.login import UserMixin

from webapp import app
from webapp import db

from webapp.models.mixins import CRUDMixin
from webapp.libs.coinbase import coinbase_checker
from webapp.libs.pool import pool_connect
from webapp.libs.utils import generate_token, ngrok_checker
from webapp.libs.geoip import get_geodata

from webapp.models.flavors import Flavors

from utter_libs.schemas.model_mixin import ModelSchemaMixin
from utter_libs.schemas import schemas

# includes user, twitterbot, openstack, appliance, status models

# user model
class User(UserMixin, CRUDMixin,  db.Model, ModelSchemaMixin):
	__tablename__ = 'users'
	id = db.Column(db.Integer, primary_key=True)
	username = db.Column(db.String(100), unique=True)
	password = db.Column(db.String(100), unique=True)

	def __init__(self, username=None, password=None):
		self.username = username
		self.password = password

	def __repr__(self):
		return '<Username %r>' % (self.username)


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
					timeout = 10
				)
			except:
				app.logger.info("OpenStack API is not ready.")
				return False
		else:
			app.logger.info("OpenStack API is not ready.")
			return False
		
		return True


# appliance model
class Appliance(CRUDMixin, db.Model, ModelSchemaMixin):
	__tablename__ = 'appliance'
	id = db.Column(db.Integer, primary_key=True)
	# make it private to decorate and check for hidden flag
	_apitoken = db.Column(db.String(100), unique=True)
	ngroktoken = db.Column(db.String(100), unique=True)
	subdomain = db.Column(db.String(100), unique=True)
	dynamicimages = db.Column(db.Integer)
	secret = db.Column(db.String(100), unique=True)
	cbapikey = db.Column(db.String(100), unique=True)
	cbapisecret = db.Column(db.String(100), unique=True)
	latitude = db.Column(db.String(100), unique=True)
	longitude = db.Column(db.String(100), unique=True)
	local_ip = db.Column(db.String(100), unique=True)
	enable_image_caching = db.Column(db.Boolean(), default=True)
	object_schema = schemas['ApplianceSchema']
	hide_token = False

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
		local_ip=None,
		enable_image_caching=True,
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

	# export the local apitoken only if it's not set to be hidden
	@property
	def apitoken(self):
		if self.hide_token == False:
			return self._apitoken
		return ""

	# set the private token via setter
	@apitoken.setter
	def apitoken(self, new_token):
		self._apitoken = new_token

	def initialize(self, ip):
		# generate a new API token
		self.apitoken = generate_token()

		# remainder of settings
		self.ngroktoken = ""
		self.subdomain = ""
		self.dynamicimages = 1
		# important, do not remove
		self.secret = generate_token(size=8, caselimit=True) # not used.  having fun yet?  
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

	# version property to match appliance api schema
	@property
	def version(self):
		return app.config['VERSION']

	def token_refresh(self):
		self.apitoken = generate_token(size=64)

	def build_tunnel_conf(self):
		# move file to backup
		tunnel_conf_file = '%s/%s' % (app.config['BASE_PATH'], app.config['POOL_TUNNEL_CONF'])

		# create yaml object and write to file
		# only do this if all user entered values are ready to role
		if self.cbapikey and self.cbapisecret:
			# set development port if we are in debug mode
			if app.config['DEBUG']:
				port = app.config['DEV_PORT']
			else:
				port = 80

			# create data structure for yaml file
			data = dict(
				inspect_addr = "disabled",
				auth_token = self.ngroktoken.encode('ascii','ignore'),
				tunnels = dict(
					utterio = dict(
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

			app.logger.info("Wrote Ngrok configuration file to %s." % tunnel_conf_file)

# twitter settings model


# settings check model
class Status(CRUDMixin, db.Model):
	__tablename__ = 'status'
	id = db.Column(db.Integer, primary_key=True)
	updated = db.Column(db.Integer)
	openstack_check = db.Column(db.Integer)
	coinbase_check = db.Column(db.Integer)
	ngrok_check = db.Column(db.Integer)
	flavors_check = db.Column(db.Integer)
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
			app.logger.info("Running full status check.")
			
			# openstack connected?
			openstack_check = openstack.check()
			status.openstack_check = openstack_check

			# coinbase tokens working?
			coinbase_check = coinbase_checker(appliance)
			status.coinbase_check = coinbase_check

			# token valid?
			response = pool_connect(method='authorization', appliance=appliance)

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

			status.update()
		
		else:
			# app.logger.info("Running partial status check.")
			
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

			# update
			status.update()

		# build the response object
		settings = {
			"flavors": status.flavors_check,
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
			status.delete(status)
