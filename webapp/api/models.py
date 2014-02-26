import json

from webapp import db
from webapp.mixins import CRUDMixin
from webapp.libs.utils import server_connect, row2dict

# instances object
class Instances(CRUDMixin, db.Model):
	__tablename__ = 'instances'
	id = db.Column(db.Integer, primary_key=True)
	created = db.Column(db.Integer)
	updated = db.Column(db.Integer) 
	expires = db.Column(db.Integer)
	osflavorid = db.Column(db.String(100))
	osimageid = db.Column(db.String(100))
	publicipv4 = db.Column(db.String(100))
	publicipv6 = db.Column(db.String(100))
	ssltunnel = db.Column(db.String(400))
	osinstanceid = db.Column(db.String(100))
	name = db.Column(db.String(100))
	
	state = db.Column(db.Integer) 
	# instance state is one of:
	# 0 - inactive
	# 1 - payment address available
	# 2 - payment observed from callback
	# 3 - instance running
	# 4 - instance halted
	# 5 - instance decommissioned
	
	token = db.Column(db.String(100))
	paymentaddress = db.Column(db.String(100))

	# hourly rate in micro BTC
	hourlyrate = db.Column(db.Integer)

	def __init__(self, 
		created=None,
		updated=None,
		expires=None,
		osflavorid=None,
		osimageid=None,
		publicipv4=None,
		publicipv6=None,
		ssltunnel=None,
		osinstanceid=None,
		name=None,
		state=None,
		token=None,
		paymentaddress=None,
		hourlyrate=None,
	):
		self.created = created
		self.updated = updated
		self.expires = expires
		self.osflavorid = osflavorid
		self.osimageid = osimageid
		self.publicipv4 = publicipv4
		self.publicipv6 = publicipv6
		self.ssltunnel = ssltunnel
		self.osinstanceid = osinstanceid
		self.name = name
		self.state = state
		self.token = token
		self.paymentaddress = paymentaddress
		self.hourlyrate = hourlyrate

	def get_by_token(self, token):
		instance = db.session.query(Instances).filter_by(token=token).first()
		return instance

	def __repr__(self):
		return '<Instance Address %r>' % (self.name)

# images object
class Images(CRUDMixin,  db.Model):
	__tablename__ = 'images'
	id = db.Column(db.Integer, primary_key=True)
	osid = db.Column(db.String(100))
	md5 = db.Column(db.String(100), unique=True)
	name = db.Column(db.String(100), unique=True)
	url = db.Column(db.String(400), unique=True)
	diskformat = db.Column(db.String(100))
	containerformat = db.Column(db.String(100))
	size = db.Column(db.Integer)
	flags = db.Column(db.Integer)
	active = db.Column(db.Integer) # 0 - not active, 1 - installing, 2 - active

	def __init__(self, osid=None, md5=None, name=None, url=None, size=None, diskformat=None, containerformat=None, flags=None):
		self.osid = osid
		self.md5 = md5
		self.name = name
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

	def sync(self, apitoken):
		# grab image list from pool server
		response = server_connect(method="images", apitoken=apitoken)

		if response['response'] == "success":
			remoteimages = response['result']

			# update database for images
			for remoteimage in remoteimages['images']:
				image = db.session.query(Images).filter_by(md5=remoteimage['md5']).first()
				
				if image is None:
					# we don't have the image coming in from the server
					image = Images()

					# create a new image
					image.md5 = remoteimage['md5']
					image.name = remoteimage['name']
					image.url = remoteimage['url']
					image.size = remoteimage['size']
					image.diskformat = remoteimage['diskformat']
					image.containerformat = remoteimage['containerformat']
					image.active = 0
					image.flags = remoteimage['flags']

					# add and commit
					image.update(image)

				else:        
					# check if we need to delete image from local db
					if remoteimage['flags'] == 9:
						image.delete(image)

					# update image from remote images
					image.md5 = remoteimage['md5']
					image.name = remoteimage['name']
					image.url = remoteimage['url']
					image.size = remoteimage['size']
					image.diskformat = remoteimage['diskformat']
					image.containerformat = remoteimage['containerformat']
					image.flags = remoteimage['flags']
					
					# udpate
					image.update(image)

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


# flavors object
class Flavors(CRUDMixin,  db.Model):
	__tablename__ = 'flavors'
	id = db.Column(db.Integer, primary_key=True)
	osid = db.Column(db.String(100))
	name = db.Column(db.String(100), unique=True)
	comment = db.Column(db.String(200), unique=True)
	vpu = db.Column(db.Integer)
	mem = db.Column(db.Integer)
	disk = db.Column(db.Integer)
	flags = db.Column(db.Integer)
	active = db.Column(db.Integer)

	def __init__(self, name=None, osid=None, comment=None, vpu=None, mem=None, disk=None, flags=None, active=None):
		self.name = name
		self.osid = osid
		self.comment = comment
		self.vpu = vpu
		self.mem = mem
		self.disk = disk
		self.flags = flags
		self.active = active

	def __repr__(self):
		return '<Flavor %r>' % (self.name)

	def check(self):
		flavors = db.session.query(Flavors).all()

		# minimum one flavor installed?
		flavor_active = False

		for flavor in flavors:
			if flavor.active:
				flavor_active = True

		return flavor_active

	def sync(self, apitoken):
		# grab image list from pool server
		response = server_connect(method="flavors", apitoken=apitoken)

		if response['response'] == "success":
			remoteflavors = response['result']

			# update the database with the flavors
			for remoteflavor in remoteflavors['flavors']:
				flavor = db.session.query(Flavors).filter_by(name=remoteflavor['name']).first()
				if flavor is None:
					# we don't have the flavor coming in from the server
					flavor = Flavors()

					# create a new flavor
					flavor.name = remoteflavor['name']
					flavor.comment = remoteflavor['comment']
					flavor.vpu = remoteflavor['vpu']
					flavor.mem = remoteflavor['mem']
					flavor.disk = remoteflavor['disk']
					flavor.flags = remoteflavor['flags']
					flavor.active = 0

					# add and commit
					flavor.update(flavor)
				else:
					# we have the flavor already, so update

					# check if we need to delete image from local db
					if remoteflavor['flags'] == 9:
						flavor.delete(flavor)
						continue

					# update existing flavor
					flavor.name = remoteflavor['name']
					flavor.comment = remoteflavor['comment']
					flavor.vpu = remoteflavor['vpu']
					flavor.mem = remoteflavor['mem']
					flavor.disk = remoteflavor['disk']
					flavor.flags = remoteflavor['flags']
					
					# udpate
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

