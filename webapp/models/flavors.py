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
	network = db.Column(db.Integer)
	rate = db.Column(db.Integer)
	ask = db.Column(db.Integer)
	hot = db.Column(db.Integer)
	launches = db.Column(db.Integer)
	flags = db.Column(db.Integer)
	# possible values are:
	# 8 - deleted on pool, needs to be deleted on appliance and OpenStack
	# 4 - deleted on openstack, needs to be deleted locally and on pool
	# 2 - created on openstack, needs to be created on pool
	# 0 - all well, nothing to be done
	active = db.Column(db.Integer)
	source = db.Column(db.Integer)
	# possible sources are:
	# 0 - pool
	# 1 - openstack cluster

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
		hot=None,
		launches=None,
		flags=None,
		active=None,
		source=None
	):
		self.name = name
		self.osid = osid
		self.description = description
		self.vpus = vpus
		self.memory = memory
		self.disk = disk
		self.network = network
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

	def sync_from_openstack(self, appliance):
		from webapp.libs.openstack import list_flavors

		response = list_flavors(filter_by='stackmonkey')
		if response['response'] == "error":
			app.logger.error("Failed to list flavors from OpenStack cluster")
			return

		osflavors = response['result']['flavors']

		# create all the non-existent ones
		for osflavor in osflavors:
			oskeys = osflavor.get_keys()
			try:
				ask_price = int(oskeys['stackmonkey'])
			except ValueError:
				continue
			flavor = db.session.query(Flavors).filter_by(name=osflavor.name).first()
			if not flavor:
				flavor = Flavors()
				flavor.flags = 2
			flavor.osid = osflavor.id
			flavor.source = 1 # source is openstack cluster
			flavor.ask = ask_price
			flavor.description = 'synced from openstack'
			flavor.name = osflavor.name
			flavor.vpus = osflavor.vcpus
			flavor.memory = osflavor.ram
			flavor.disk = osflavor.disk
			# flavor.hot = remoteflavor['hot']
			flavor.launches = 0
			flavor.active = 1
			flavor.hot = 2
			flavor.rate = 0
			if 'quota:outbound_average' in oskeys.keys():
				flavor.network = oskeys['quota:outbound_average']
			else:
				flavor.network = 1
			flavor.save()

		osflavor_names = [x.name for x in osflavors]
		# mark all flavors that came from openstack but are deleted now
		for flavor in db.session.query(Flavors).filter_by(source=0):
			if flavor.name not in osflavor_names:
				flavor.flags = 4
				flavor.save()

		# execute all actions necessary to sync pool and openstack
		for flavor in Flavors.get_all():

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

	def sync(self, appliance):
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


