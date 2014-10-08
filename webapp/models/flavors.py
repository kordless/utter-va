import json

from webapp import app
from webapp import db

from webapp.models.mixins import CRUDMixin

from webapp.libs.utils import generate_token
from webapp.libs.pool import pool_connect
from webapp.libs.pool import PoolApiFlavorsList
from webapp.libs.pool import PoolApiException

from utter_libs.schemas.model_mixin import ModelSchemaMixin
from utter_libs.schemas.helpers import ApiSchemaHelper
from utter_libs.schemas import schemas

# flavors model
class Flavors(CRUDMixin,  db.Model, ModelSchemaMixin):
	__tablename__ = 'flavors'
	id = db.Column(db.Integer, primary_key=True)
	osid = db.Column(db.String(100))
	name = db.Column(db.String(100), unique=True)
	description = db.Column(db.String(200))
	vpus = db.Column(db.Integer)
	memory = db.Column(db.Integer)
	disk = db.Column(db.Integer)
	network_down = db.Column(db.Integer)
	network_up = db.Column(db.Integer)
	rate = db.Column(db.Integer)
	ask = db.Column(db.Integer)
	hot = db.Column(db.Integer)
	launches = db.Column(db.Integer)
	flags = db.Column(db.Integer)
	# possible values are:
	# 8 - deleted on pool, needs to be deleted on appliance and OpenStack
	# 4 - deleted on openstack, needs to be deleted locally and on pool
	# 0 - all well, nothing to be done
	active = db.Column(db.Boolean)
	locality = db.Column(db.Integer)
	# possible localities are:
	# 0 - originated on pool and not installed locally (excluding merges)
	# 1 - openstack cluster
	# 2 - synced from pool and not installed locally (including merges)
	# 3 - synced from pool and installed locally (including merges)

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
		('ask', 'extra_spec:int:stackmonkey:ask_price')]

	# which schema should be used for validation and serialization
	object_schema = schemas['FlavorSchema']

	def __init__(
		self,
		name=None,
		osid=None,
		description=None,
		vpus=None,
		memory=None,
		disk=None,
		# the default network limitation if none is specified is 1
		network_down=-1,
		network_up=-1,
		# the default price and rate is 0 if nothing is passed
		rate=0,
		ask=0,
		# default hot value should be 2, because we feel like it
		hot=2,
		launches=0,
		flags=None,
		# flavors are only active if activated
		active=0,
		locality=None
	):
		self.name = name
		self.osid = osid
		self.description = description
		self.vpus = vpus
		self.memory = memory
		self.disk = disk
		self.network_down = network_down
		self.network_up = network_up
		# rate is the price this flavor has been sold for in the past
		self.rate = rate
		# ask the price that this flavor costs
		self.ask = ask
		self.hot = hot
		self.launches = launches
		self.flags = flags
		self.active = active
		self.locality = locality

	def __repr__(self):
		return '<Flavor %r>' % (self.name)

	@property
	def installed(self):
		if self.locality == 2:
			return False
		return True

	# retreive the ask price of this flavor that's set on openstack via keys
	@property
	def ask_on_openstack(self):
		from webapp.libs.openstack import get_flavor_keys
		if not self.osid:
			return
		keys = get_flavor_keys(self.osid)
		if not 'stackmonkey:ask_price' in keys:
			return
		return int(keys['stackmonkey:ask_price'])

	def _get_sync_hooks(self):
		# return sync hooks for property updates
		return {'ask': self._sync_ask_price}

	# sync hook to push ask price to open stack on update
	def _sync_ask_price(self):
		from webapp.libs.openstack import set_flavor_ask_price

		# if flavor doesn't exist on openstack we don't need to attempt to update it
		if not self.osid:
			return

		# if price on openstack is already equal to new price just return
		if self.ask == self.ask_on_openstack:
			return

		# attempt to update openstack with the correct price
		try:
			set_flavor_ask_price(self.osid, self.ask)
		except Exception as e:
			app.logger.info("Failed to update flavor=(%s) price on cluster. %s" % (self.name, str(e)))

		return

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

	def sync_from_openstack(self, appliance):
		from webapp.libs.openstack import list_flavors

		# get all flavors that have the stackmonkey:ask_price key set in their extra_specs
		response = list_flavors()
		if response['response'] == "error":
			app.logger.error("Failed to list flavors from OpenStack cluster.")
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
				flavor.locality = 1
				flavor.copy_values_from_osflavor(osflavor)
				# if a price is given, activate the new flavor
				if flavor.ask > 0:
					flavor.active = True
					flavor.save(ignore_hooks=True)
			else:
				if not flavor.is_same_as_osflavor(osflavor):
					# flavor has changed
					flavor.copy_values_from_osflavor(osflavor)
					flavor.flags = 0
					flavor.save(ignore_hooks=True)

		osflavor_ids = [x.id for x in osflavors]
		# delete all flavors that originally came from openstack but are deleted now
		for flavor in db.session.query(Flavors).filter_by(locality=1):
			if flavor.osid not in osflavor_ids:
				flavor.flags = 4
				flavor.delete()

	def sync(self):
		response = {'response': 'success', 'result': ''}

		try:
			# validate the returned dictionary and unpack it into a dictionary
			flavor_list_schema = schemas['FlavorListSchema']().from_json(
				# grab flavor list from pool server
				PoolApiFlavorsList().request())
		except ValueError:
			app.logger.error("Received a broken format for flavors from pool.")
			return
		except PoolApiException as e:
			app.logger.error(str(e))
			return

		# update the database with the flavors
		for flavor_schema in flavor_list_schema.items:
			# in case of update we will want to keep certain values
			keep_values = {}

			flavor = db.session.query(Flavors).filter_by(
				name=flavor_schema.name.as_dict()).first()

			# check if we need to delete flavor from local db
			# b'001000' indicates delete flavor
			# TODO: need to cleanup OpenStack flavor if we uninstall
			if (flavor_schema.flags.as_dict() & 8) == 8 and flavor != None:
				# only delete if we have it
				flavor.delete()
				continue

			elif flavor is None:
				# we don't have the flavor that's coming in from the pool
				flavor = Flavors()
			else:
				# if active and installed on openstack, do not update price
				if flavor.active == True and flavor.locality == 3:
					# do not change ask price if flavor is enabled
					flavor_schema.ask = None
				# active flag should never be updated by pool
				flavor_schema.active = None

			ApiSchemaHelper.fill_object_from_schema(flavor_schema, flavor)

			flavor.save()

		# overwrite the results with the list of current flavors as dicts
		response['result'] = {
			'flavors': [
				x.as_schema().as_dict()
				for x in db.session.query(Flavors).all()]
		}
		
		return response


