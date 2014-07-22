import md5

from urlparse import urlparse

from webapp import app
from webapp import db

from webapp.models.mixins import CRUDMixin
from webapp.libs.coinbase import coinbase_generate_address, coinbase_get_addresses, coinbase_checker

from webapp.libs.utils import generate_token, row2dict
from webapp.models.models import Appliance, Status

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
		# grab addresses from coinbase
		response = coinbase_get_addresses(appliance=appliance)

		if response['response'] == "success":
			remoteaddresses = response['result']['addresses']

			# update database with remote addresses
			for remoteaddress_address in remoteaddresses:
				# work around coinbase's strange address:address thing
				remoteaddress = remoteaddress_address['address']

				print remoteaddress

				# check if address label is the md5 of our coinbase api key
				if remoteaddress['label'] == md5.new(appliance.cbapikey).hexdigest():

					# see if we have a matching address
					address = db.session.query(Addresses).filter_by(address=remoteaddress['address']).first()
					
					# we don't have the address at coinbase in database
					if address is None:
						# create a new address
						address = Addresses()
						address.address = remoteaddress['address']
						address.token = urlparse(remoteaddress['callback_url']).path.split('/')[-1]
						address.instance_id = 0 # no instances yet
						address.subdomain = urlparse(remoteaddress['callback_url']).hostname.split('.')[0]

						# add and commit
						address.update(address)

					# we have the address already and need to update it
					else:
						# update address from remote addresses
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
			app.logger.error("Error contacting Coinbase during sync.")
			# lift respose from server call to view
			return response

	# assign a bitcoin address for use with an instance
	def assign(self, instance_id):
		# check if the instance id is already assigned to an address (just in case)
		address = db.session.query(Addresses).filter_by(instance_id=instance_id).first()
		
		# appliance object
		appliance = db.session.query(Appliance).first()

		# if we found an address, update and return it
		if address:
			address.instance_id = instance_id
			address.update(address)
			return address

		else:
			# check if we have an empty address to assign
			address = db.session.query(Addresses).filter_by(instance_id=0).first()		

			# we found one, so assign instance_id
			if address:
				# assign the instance id to the address
				address.instance_id = instance_id
				address.update(address)
				return address

			else:
				# need a new address at this point
				# check if coinbase connection is live
				settings = Status().check_settings()
				if not settings['coinbase']:
					return None

				# check if appliance has a subdomain assigned
				if not appliance.subdomain:
					return None

				# now ask coinbase for new address and set callback
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

					app.logger.info("Allocated new Coinbase address=(%s) to an instance." % address.address)
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
		app.logger.info("Released address=(%s) from instance." % self.address)
		return self
