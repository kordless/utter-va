import re
import urllib2

from webapp import db

from webapp.models.mixins import CRUDMixin
from webapp.models.models import Appliance

from webapp.libs.openstack import glance_client
from webapp.libs.openstack import create_os_image
from webapp.libs.openstack import ensure_image_is_deleted

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
		proto_search = re.compile('^http[s]{0,1}://(.*)$').search(urlinfo.url)
		if proto_search:
			cropped_url = proto_search.group(1)
		else:
			cropped_url = self.url
		return 'http://' + Appliance.get().local_ip + ':8080/' + cropped_url

	def save(self, *args, **kwargs):
		os_image = create_os_image(name=self.name, url=self.cached_url)
		self.osid = os_image.id
		super(Images, self).save(*args, **kwargs)

	def delete(self, *args, **kwargs):
		ensure_image_is_deleted(self.osid)
		super(Images, self).delete(*args, **kwargs)

	def housekeeping(self):
		if self.instances.count() == 0:
			self.delete()
