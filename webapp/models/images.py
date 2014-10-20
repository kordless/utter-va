import re
from bz2 import BZ2Decompressor
import urllib2
import requests

from glanceclient import exc as glance_exceptions
from glanceclient.common.utils import get_data_file

from webapp import db
from webapp import app

from webapp.models.mixins import CRUDMixin
from webapp.models.models import Appliance

from webapp.libs.openstack import glance_client
from webapp.libs.openstack import create_os_image
from webapp.libs.openstack import ensure_image_is_deleted
from webapp.libs.openstack import os_image_exists
from webapp.libs.openstack import get_os_image

# images model
class Images(CRUDMixin, db.Model):
	__tablename__ = 'images'
	osid = db.Column(db.String(100))
	url = db.Column(db.String(1024), unique=True)
	name = db.Column(db.String(1024))
	container_format = db.Column(db.String(1024))
	disk_format = db.Column(db.String(1024))
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
			url = 'http://{0}:8080/{1}/{2}'.format(Appliance.get().local_ip, proto, host_path)
		else:
			url = self.url
		return url

	@property
	def status(self):
		if not self.osid:
			return ''
		return get_os_image(self.osid).status

	@property
	def decompress(self):
		return bool(
			re.compile(
				'\.bz2$'
			).search(
				self.cached_url))

	def save(self, *args, **kwargs):
		if Appliance.get().enable_image_caching and (
				self.osid == None or not os_image_exists(self.osid)):
			if self.decompress:
				self.osid = self.proxy_image(compressed=True)
			else:
				self.osid = create_os_image(
					name=self.name,
					url=self.cached_url,
					disk_format=self.disk_format,
					container_format=self.container_format).id
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

	def get_data_stream(self, compressed=False):
		data = requests.get(
				self.cached_url,
				stream=True
			).raw.data
		if compressed:
			app.logger.error("Decompressing compressed Image.")
			data = BZ2Decompressor().decompress(data)
		return data

	def proxy_image(self, compressed=False):
		osid = create_os_image(
			name=self.name,
			url=self.cached_url,
			fd=self.get_data_stream(compressed=compressed)).id
		self.update(osid=osid)
