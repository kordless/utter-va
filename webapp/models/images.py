import time
import md5

from urllib2 import urlopen

from webapp import app
from webapp import db

from webapp.models.mixins import CRUDMixin

from webapp.libs.utils import row2dict, generate_token
from webapp.libs.pool import pool_connect
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

	def save(self, *args, **kwargs):
		os_image = create_os_image(name=self.name, url=self.url)
		self.osid = os_image.id
		super(Images, self).save(*args, **kwargs)

	def delete(self, *args, **kwargs):
		ensure_image_is_deleted(self.osid)
		super(Images, self).delete(*args, **kwargs)

	def housekeeping(self):
		if self.instances.count() == 0:
			self.delete()
