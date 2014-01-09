from webapp import db, bcrypt
from webapp.mixins import CRUDMixin
from werkzeug import generate_password_hash, check_password_hash

# openstack database
class Openstack(CRUDMixin,  db.Model):
    __tablename__ = 'openstack'
    id = db.Column(db.Integer, primary_key=True)

    authurl = db.Column(db.String(100))
    tenantname = db.Column(db.String(100))
    tenantid = db.Column(db.String(100))
    username = db.Column(db.String(100))
    password = db.Column(db.String(100))
 
    def __init__(self, authurl=None, tenantname=None, tenantid=None, username=None):
    	self.authurl = authurl
    	self.tenantname = tenantname
    	self.tenantid = tenantid
        self.username = username

    def __repr__(self):
        return '<TenantID %r>' % (self.tenantid)