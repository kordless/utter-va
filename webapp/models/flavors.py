import json

from sqlalchemy import exc as sa_exceptions
from webapp import app
from webapp import db

from novaclient import exceptions as nova_exceptions

from webapp.models.mixins import CRUDMixin

from webapp.libs.utils import generate_token
from webapp.libs.pool import pool_connect
from webapp.libs.pool import PoolApiFlavorsList
from webapp.libs.pool import PoolApiException
from webapp import models

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
	# max count of instances that can be created of a flavor
	max_instances = db.Column(db.Integer)
	flags = db.Column(db.Integer)
	# possible values are:
	# 8 - deleted on pool, needs to be deleted on appliance and OpenStack
	# 4 - deleted on openstack, needs to be deleted locally and on pool
	# 0 - all well, nothing to be done

	# relationships
	instances = db.relationship('Instances', backref='flavor', lazy='dynamic')
	
	# active defines whether instances of this flavor should be generated or not
	active = db.Column(db.Boolean)
	# installed is True if:
	# 1) flavor of equal specs exists on OpenStack
	# 2) the id of this flavor is set on osid
	installed = db.Column(db.Boolean)

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

	# these values are used when an openstack flavor does not define them
	default_property_values = {
		'quota:inbound_average': 0,
		'quota:outbound_average': 0,
		'stackmonkey:ask_price': 0}

	# which schema should be used for validation and serialization
	object_schema = schemas['FlavorSchema']

	# criteria based on which we decide if another flavor is same or not
	comparison_criteria = [
		{'key': 'memory', 'name': 'm'},
		{'key': 'vpus', 'name': 'v'},
		{'key': 'disk', 'name': 'd'},
		{'key': 'network_up', 'name': 'e'},  # e = egress
		{'key': 'network_down', 'name': 'i'}]  # i = ingress

	def __init__(
		self,
		name=None,
		osid=None,
		description=None,
		vpus=None,
		memory=None,
		disk=None,
		# the default network limitation if none is specified is -1
		network_down=0,
		network_up=0,
		# the default price and rate is 0 if nothing is passed
		rate=0,
		ask=0,
		# default hot value should be 2, because we feel like it
		hot=2,
		max_instances=None,
		launches=0,
		flags=0,
		# flavors are only active if activated
		active=False,
		installed=False
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
		self.max_instances = hot if max_instances is None else max_instances
		self.launches = launches
		self.flags = flags
		self.active = active
		self.installed = installed

	def __repr__(self):
		return '<Flavor %r>' % (self.name)

	# retreive the ask price of this flavor that's set on openstack via keys
	@property
	def ask_on_openstack(self):
		from webapp.libs.openstack import get_flavor_keys
		if not self.osid:
			return
		try:
			keys = get_flavor_keys(self.osid)
		except nova_exceptions.NotFound:
			# nebula only
			return
		if not 'stackmonkey:ask_price' in keys:
			return
		return int(keys['stackmonkey:ask_price'])

	def _get_sync_hooks(self):
		# return sync hooks for property updates
		return {
			'ask': self._sync_ask_price,
			'active': self._update_active,
			'installed': self._update_installed,
			'max_instances': self._update_max_instances}

	# sync hook to push ask price to open stack on update
	def _sync_ask_price(self):
		from webapp.libs.openstack import set_flavor_ask_price

		# if flavor doesn't exist on openstack we don't need to attempt to update it
		if not self.osid or not self.installed or not self.active:
			return

		try:
			# if price on openstack is already equal to new price just return
			if self.ask == self.ask_on_openstack:
				return

			set_flavor_ask_price(self.osid, self.ask)
		except Exception as e:
			app.logger.warning("Failed to update flavor=(%s) price on cluster. %s" % (self.name, str(e)))

	def _update_active(self):
		if not self.active:
			for instance in self.instances:
				if not instance.running:
					instance.deactivate()
		elif self.installed:
			models.instances.Instances().mix(self)

	def _update_installed(self):
		if not self.installed:
			for instance in self.instances:
				if not instance.running:
					instance.delete()
		elif self.active and self.installed and self.ask > 0:
			models.instances.Instances().mix(self)

	def _update_max_instances(self):
		if self.active and self.installed and self.ask > 0:
			models.instances.Instances().mix(self)

	@classmethod
	def get_by_specs(cls, *args, **kwargs):
		criteria = dict(
			(crit_key, kwargs[crit_key])
			for crit_key in [
					crit_full['key']
					for crit_full in cls.comparison_criteria])
		return Flavors.query.filter_by(**criteria).first()

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
		from webapp.libs.openstack import get_flavor_keys
		key_spec = "extra_spec:"
		try:
			keys = get_flavor_keys(flavor.id)
		except nova_exceptions.NotFound:
			# nebula only
			keys = {}
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
					try:
						ret_value[property[0]] = self.default_property_values[property_chunks[2]]
					except KeyError:
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
			os_flavor_values = self.get_values_from_osflavor(osflavor)
			flavor = self.get_by_specs(**os_flavor_values)
			if not flavor:
				# flavor is new
				flavor = Flavors(**os_flavor_values)
				flavor.installed = True
				# if a price is given, activate the new flavor
				if flavor.ask > 0:
					flavor.active = True
				flavor.save()
			else:
				flavor.installed = True
				flavor.osid = osflavor.id
				flavor.flags = 0
				flavor.name = os_flavor_values['name']
				if os_flavor_values.has_key('ask') and os_flavor_values['ask'] != 0:
					flavor.ask = os_flavor_values['ask']
				try:
					flavor.save()
					db.session.flush()
				except (sa_exceptions.IntegrityError, sa_exceptions.OperationalError) as e:
					app.logger.error('Exception when saving flavor "{0}": "{1}".'.format(
						osflavor.name, str(e)))

		# find all flavors that are currently installed == True, but are not in the
		# list of flavor that came back from openstack. set all of them to be
		# installed = False
		osflavor_ids = [x.id for x in osflavors]
		for flavor in db.session.query(Flavors).filter_by(installed=True):
			if flavor.osid not in osflavor_ids:
				flavor.update(installed=False, osid=None)

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
			flavor = self.get_by_specs(**flavor_schema.as_dict())

			# check if we need to delete flavor from local db
			# b'001000' indicates delete flavor
			# TODO: need to cleanup OpenStack flavor if we uninstall
			if (flavor_schema.flags.as_dict() & 8) == 8:
				# only delete if we have it
				if flavor != None:
					flavor.delete()
				continue

			elif flavor is None:
				# don't have it, create, and set not active
				flavor = Flavors()
				exception_keys = ['active']
			else:
				exception_keys = ['active', 'ask', 'name']
				
			# populate the object
			ApiSchemaHelper.fill_object_from_schema(
				flavor_schema,
				flavor,
				exceptions=exception_keys)

			try:
				flavor.save()
				db.session.flush()
			except (sa_exceptions.IntegrityError, sa_exceptions.OperationalError):
				app.logger.error('Exception when saving flavor "{0}": "{1}".'.format(
					osflavor.name, str(e)))

		# overwrite the results with the list of current flavors as dicts
		response['result'] = {
			'flavors': [
				x.as_schema().as_dict()
				for x in db.session.query(Flavors).all()]
		}
		
		return response
