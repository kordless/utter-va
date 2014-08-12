import time
import md5

from urllib2 import urlopen

from webapp import app
from webapp import db

from webapp.models.mixins import CRUDMixin

from webapp.libs.utils import row2dict, generate_token
from webapp.libs.images import uninstall_image
from webapp.libs.pool import pool_connect

# images model
class Images(CRUDMixin, db.Model):
	__tablename__ = 'images'
	id = db.Column(db.Integer, primary_key=True)
	osid = db.Column(db.String(100))
	created = db.Column(db.Integer)
	updated = db.Column(db.Integer)
	name = db.Column(db.String(100), unique=True)
	description = db.Column(db.String(200))
	url = db.Column(db.String(1024), unique=True)
	local_url = db.Column(db.String(1024), unique=True)
	diskformat = db.Column(db.String(100))
	containerformat = db.Column(db.String(100))
	size = db.Column(db.Integer)
	cache = db.Column(db.Integer) 

	# 8 - uninstall
	flags = db.Column(db.Integer)

	# 0 - not installed/error, 1 - know about it, 2 - installing, 3 - installed
	active = db.Column(db.Integer)

	def __init__(
		self, 
		osid=None,
		created=None,
		updated=None,
		name=None, 
		description=None, 
		url=None,
		local_url=None,
		size=None, 
		cache=None,
		diskformat=None, 
		containerformat=None, 
		flags=None
	):
		self.osid = osid
		self.created = created
		self.updated = updated
		self.name = name
		self.description = description
		self.url = url
		self.local_url = local_url
		self.size = size
		self.cache = cache
		self.diskformat = diskformat
		self.containerformat = containerformat
		self.flags = flags
	
	def __repr__(self):
		return '<Image %r>' % (self.name)

	# create a dynamic image from an instance
	def get_or_create_by_instance(self, instance):
		# check if we already have it
		image_name = "dynamic_image_%s" % md5.md5(instance.dynamic_image_url).hexdigest()
		image = db.session.query(Images).filter_by(name=image_name).first()

		# return it if we have it
		if image:
			return image

		# else make a new one
		try:
			image = Images()
			epoch_time = int(time.time())
			image.created = epoch_time
			image.updated = epoch_time
			image.name = image_name # from above
			image.description = "Dynamic Image for Instance %s" % instance.name
			image.url = instance.dynamic_image_url

			# connect to remote URL's site and get size
			site = urlopen(instance.dynamic_image_url)
			meta = site.info()

			try:
				size = int(meta.getheaders("Content-Length")[0])
			except:
				size = 0 # unknown size

			site.close()

			image.size = size
			image.cache = 0 # don't cache
			image.diskformat = "qcow2" # no time for anything fancy here
			image.containerformat = "bare"
			image.active = 1
			image.flags = 1

			# add and commit
			image.update(image)

			# return the image
			return image
		
		except Exception as ex:
			app.logger.error("Failed to install image=(%s) into the OpenStack cluster. %s." % (image_name, ex))
			return None

	def housekeeping(self):
		# limited time, all of us
		epoch_time = int(time.time())

		# delete if older than configured amount 
		if self.created + app.config['POOL_DYNAMIC_IMAGES_EXPIRE_TIME'] < epoch_time:
			# only delete images which were specified not to be cached (probably dynamic)
			if not self.cache:
				# openstack call to delete
				from webapp.libs.openstack import image_delete
				image_delete(self)

				# delete from datastore
				self.delete(self)

		return True

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
		response = pool_connect(method="images", appliance=appliance)

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
					epoch_time = int(time.time())
					image.created = epoch_time
					image.updated = epoch_time
					image.name = remoteimage['name']
					image.description = remoteimage['description']
					image.url = remoteimage['url']
					image.size = remoteimage['size'] # used as a suggestion of size only
					image.cache = 1 # cache locally (unlike dynamic images)
					image.diskformat = remoteimage['diskformat']
					image.containerformat = remoteimage['containerformat']
					image.active = 1 # indicates we know about it, but not downloaded
					image.flags = remoteimage['flags']

					# add and commit
					image.update(image)

				else:
					# update image from remote images (local lookup was by name)
					epoch_time = int(time.time())
					image.description = remoteimage['description']
					if image.url != remoteimage['url']:
						image.url = remoteimage['url']
						image.updated = epoch_time
					if image.diskformat != remoteimage['diskformat']:
						image.diskformat = remoteimage['diskformat']
						image.updated = epoch_time
					if image.containerformat != remoteimage['containerformat']:
						image.containerformat = remoteimage['containerformat']
						image.updated = epoch_time
					if image.flags != remoteimage['flags']:
						image.flags = remoteimage['flags']
						image.updated = epoch_time

					# update
					image.update(image)

			# grab a new copy of the images in database
			images = db.session.query(Images).all()

			# overload the results with the list of current images
			response['result']['images'] = []
			images = db.session.query(Images).all()

			for image in images:
				response['result']['images'].append(row2dict(image))

			return response

		# failure contacting server
		else:
			# lift respose from server call to view
			return response