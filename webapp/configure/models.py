from webapp import db, bcrypt
from webapp.mixins import CRUDMixin
from werkzeug import generate_password_hash, check_password_hash

# openstack database
class OpenStack(CRUDMixin,  db.Model):
    __tablename__ = 'openstack'
    id = db.Column(db.Integer, primary_key=True)

    authurl = db.Column(db.String(100))
    tenantname = db.Column(db.String(100), unique=True)
    tenantid = db.Column(db.String(100), unique=True)
    osusername = db.Column(db.String(100), unique=True)
    ospassword = db.Column(db.String(100))
 
    def __init__(self, authurl=None, tenantname=None, tenantid=None, osusername=None, ospassword=None):
    	self.authurl = authurl
    	self.tenantname = tenantname
    	self.tenantid = tenantid
        self.osusername = osusername
        self.ospassword = ospassword

    def __repr__(self):
        return '<TenantID %r>' % (self.tenantid)


# appliance database
class Appliance(CRUDMixin,  db.Model):
    __tablename__ = 'appliance'
    id = db.Column(db.Integer, primary_key=True)
    apikey = db.Column(db.String(100), unique=True)
    latitude = db.Column(db.String(100), unique=True)
    longitude = db.Column(db.String(100), unique=True)

    def __init__(self, apikey=None, latitude=None, longitude=None):
    	self.apikey = apikey
    	self.latitude = latitude
    	self.longitude = longitude