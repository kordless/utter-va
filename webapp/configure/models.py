import os
import yaml
import shutil

from webapp import app, db
from webapp.mixins import CRUDMixin
from webapp.libs.geoip import get_geodata
from webapp.libs.utils import generate_token
from keystoneclient.v2_0 import client as keyclient

# openstack database
class OpenStack(CRUDMixin,  db.Model):
	__tablename__ = 'openstack'
	id = db.Column(db.Integer, primary_key=True)

	authurl = db.Column(db.String(100))
	tenantname = db.Column(db.String(100), unique=True)
	tenantid = db.Column(db.String(100), unique=True)
	osusername = db.Column(db.String(100), unique=True)
	ospassword = db.Column(db.String(100))
 
	def __init__(self, authurl=None, tenantname=None, tenantid=None, osusername=None, ospassword=None):
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


# appliance database
class Appliance(CRUDMixin,  db.Model):
	__tablename__ = 'appliance'
	id = db.Column(db.Integer, primary_key=True)
	apitoken = db.Column(db.String(100), unique=True)
	ngroktoken = db.Column(db.String(100), unique=True)
	subdomain = db.Column(db.String(100), unique=True)
	secret = db.Column(db.String(100), unique=True)
	cbapikey = db.Column(db.String(100), unique=True)
	cbapisecret = db.Column(db.String(100), unique=True)
	latitude = db.Column(db.String(100), unique=True)
	longitude = db.Column(db.String(100), unique=True)

	def __init__(self, apitoken=None, ngroktoken=None, subdomain=None, secret=None, cbapikey=None, cbapisecret=None, latitude=None, longitude=None):
		self.apitoken = apitoken
		self.ngroktoken = ngroktoken
		self.subdomain = subdomain
		self.secret = secret
		self.cbapikey = cbapikey
		self.cbapisecret = cbapisecret
		self.latitude = latitude
		self.longitude = longitude

	def initialize(self):
		# generate a new API token
		self.apitoken = generate_token()

		# remainder of settings
		self.ngroktoken = ""
		self.subdomain = generate_token(size=16, caselimit=True)
		self.secret = generate_token(size=8, caselimit=True)
		self.cbapikey = ""
		self.cbapisecret = ""
		self.cbaccesstoken = ""
		self.cbrefreshtoken = ""

		# get geodata
		geo_data = get_geodata()
		self.latitude = geo_data['latitude']
		self.longitude = geo_data['longitude']
		
		# create entry
		self.update(self)

	def token_refresh(self):
		self.apitoken = generate_token(size=64)

	def check(self):
		appliance = db.session.query(Appliance).first()
		if appliance.cbapikey and appliance.cbapisecret and appliance.ngroktoken:
			return True
		else:
			print "oh noews"
			return False

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
