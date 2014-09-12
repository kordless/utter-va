from webapp import app
from webapp import db
from webapp.libs.pool import CustomFlavorsPoolApiDelete
from webapp.libs.pool import CustomFlavorsPoolApiCreate

from webapp.models.mixins import CRUDMixin

from webapp.libs.utils import generate_token, row2dict
from webapp.libs.pool import pool_connect

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
	network_up = db.Column(db.Integer)
	network_down = db.Column(db.Integer)
	rate = db.Column(db.Integer)
	ask = db.Column(db.Integer)
	hot = db.Column(db.Integer)
	launches = db.Column(db.Integer)
	flags = db.Column(db.Integer)
	# possible values are:
	# 8 - deleted on pool, needs to be deleted on appliance and OpenStack
	# 4 - deleted on openstack, needs to be deleted locally and on pool
	# 2 - created on openstack, needs to be created on pool
	# 1 - updated on openstack, needs to be updated on pool
	# 0 - all well, nothing to be done
	active = db.Column(db.Boolean)
	source = db.Column(db.Integer)
	# possible sources are:
	# 0 - pool
	# 1 - openstack cluster

	# mappings of names with openstack flavor properties and extra keys
	# used in method get_values_from_osflavor
	os_property_mapping = [
		('osid', 'id'),
		('name', 'name'),
		('vpus', 'vcpus'),
		('memory', 'ram'),
		('disk', 'disk'),
		('network_down', 'extra_spec:int:quota:inbound_average'),
		('network_up', 'extra_spec:int:quota:outbound_average'),
		('ask', 'extra_spec:int:stackmonkey')]

	def __init__(
		self,
		name=None,
		osid=None,
		description=None,
		vpus=None,
		memory=None,
		disk=None,
		# the default network limitation if none is specified is 1
		network_up=1,
		network_down=1,
		# the default price and rate is 0 if nothing is passed
		rate=0,
		ask=0,
		# default hot value should be 2, because we feel like it
		hot=2,
		launches=0,
		flags=None,
		# flavors are only active if activated
		active=0,
		source=None
	):
		self.name = name
		self.osid = osid
		self.description = description
		self.vpus = vpus
		self.memory = memory
		self.disk = disk
		self.network_up = network_up
		self.network_down = network_down
		# rate is the price this flavor has been sold for in the past
		self.rate = rate
		# ask the price that this flavor costs
		self.ask = ask
		self.hot = hot
		self.launches = launches
		self.flags = flags
		self.active = active
		self.source = source

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

	# extract values and keys from osflavor and return them as simple dict
	def get_values_from_osflavor(self, flavor):
		key_spec = "extra_spec:"
		keys = flavor.get_keys()
		ret_value = {}
		for property in self.os_property_mapping:
			if property[1][:len(key_spec)] == key_spec:
				property_chunks = property[1].split(':', 2)
				try:
					# get the specified value from keys and try to convert it to
					# the specified fromat, like int or str
					ret_value[property[0]] = eval(property_chunks[1])(
							keys[property_chunks[2]])
				except (ValueError, KeyError):
					pass
			else:
				ret_value[property[0]] = getattr(flavor, property[1])
		return ret_value

	# check if same as given openstack flavor
	def is_same_as_osflavor(self, osflavor):
		for (key, value) in self.get_values_from_osflavor(osflavor).items():
			if getattr(self, key) != value:
				return False
		return True

	# copy all properties from osflavor to self
	def copy_values_from_osflavor(self, osflavor):
		for (key, value) in self.get_values_from_osflavor(osflavor).items():
			setattr(self, key, value)
		self.save()

	def sync_openstack_to_pool(self, appliance):
		from webapp.libs.openstack import list_flavors

		# get all flavors that have the stackmonkey key set in their extra_specs
		response = list_flavors(filter_by='stackmonkey')
		if response['response'] == "error":
			app.logger.error("Failed to list flavors from OpenStack cluster")
			return
		osflavors = response['result']['flavors']

		# create all the non-existent ones
		for osflavor in osflavors:
			# if flavor doesn't exist, create new one
			flavor = db.session.query(Flavors).filter_by(name=osflavor.name).first()
			if not flavor:
				# flavor is new
				flavor = Flavors()
				flavor.flags = 2
				flavor.source = 1
				flavor.copy_values_from_osflavor(osflavor)
				# if a price is given, activate the new flavor
				if flavor.ask > 0:
					flavor.active = 1
					flavor.save()
			else:
				if not flavor.is_same_as_osflavor(osflavor):
					# flavor has changed
					flavor.copy_values_from_osflavor(osflavor)
					flavor.flags = 1
					flavor.save()

		osflavor_ids = [x.id for x in osflavors]
		# mark all flavors that originally came from openstack but are deleted now
		for flavor in db.session.query(Flavors).filter_by(source=0):
			if flavor.id not in osflavor_ids:
				flavor.flags = 4
				flavor.save()

		# execute all actions necessary to sync pool and openstack
		for flavor in Flavors.get_all():

			# sync updates from openstack to the pool
			if flavor.flags & 1 == 1:
				try:
					CustomFlavorsPoolApiUpdate(appliance).request(data={'flavor': flavor})
					flavor.flags = 0
					flavor.save()
				except:
					pass

			# create the new custom flavors on pool
			if flavor.flags & 2 == 2:
				try:
					CustomFlavorsPoolApiCreate(appliance).request(data={'flavor': flavor})
					flavor.flags = 0
					flavor.save()
				except:
					pass

			# delete custom flavors from pool
			if flavor.flags & 4 == 4:
				try:
					CustomFlavorsPoolApiDelete(appliance).request(data={'flavor': flavor})
					flavor.delete()
				except:
					pass

	def sync_pool_to_openstack(self, appliance):
		# grab image list from pool server
		response = pool_connect(method="flavors", appliance=appliance)

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
					flavor.hot = remoteflavor['hot']
					flavor.launches = remoteflavor['launches']
					flavor.flags = remoteflavor['flags']
					flavor.source = 0 # source is pool
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
					flavor.hot = remoteflavor['hot']
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


