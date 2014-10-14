import re
import urllib2

from glanceclient import exc as glance_exceptions

from webapp import db

from webapp.models.mixins import CRUDMixin
from webapp.models.models import Appliance

from webapp.libs.openstack import glance_client
from webapp.libs.openstack import create_os_image
from webapp.libs.openstack import ensure_image_is_deleted
from webapp.libs.openstack import os_image_exists

# images model
class Images(CRUDMixin, db.Model):
	__tablename__ = 'images'
	osid = db.Column(db.String(100))
	url = db.Column(db.String(1024), unique=True)
	name = db.Column(db.String(1024))
	instances = db.relationship('Instances', backref='image', lazy='dynamic')

	@property
	def cached_url(self):
		# resolve url to it's final destination
		urlinfo = urllib2.build_opener().open(urllib2.Request(self.url))

		# remove protocol from url
		proto_search = re.compile('^(http|https)://(.*)$').search(urlinfo.url)
		if proto_search:
			proto = proto_search.group(1)
			host_path = proto_search.group(2)
			url = '{0}://{1}:8080/{2}'.format(proto, Appliance.get().local_ip, host_path)
		else:
			url = self.url
			
		return url

	def save(self, *args, **kwargs):
		if Appliance.get().enable_image_caching and (
				self.osid == None or not os_image_exists(self.osid)):
			self.osid = create_os_image(name=self.name, url=self.cached_url).id
		super(Images, self).save(*args, **kwargs)

	def delete(self, *args, **kwargs):
		try:
			ensure_image_is_deleted(self.osid)
		except glance_exceptions.NotFound:
			app.logger.error("Image {0} does not exist on Glance.".format(image_id))
		super(Images, self).delete(*args, **kwargs)

	def housekeeping(self):
		if self.instances.count() == 0:
			self.delete()
