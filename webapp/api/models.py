from webapp import db
from webapp.mixins import CRUDMixin

# images database
class Images(CRUDMixin,  db.Model):
    __tablename__ = 'images'
    id = db.Column(db.Integer, primary_key=True)
    md5 = db.Column(db.String(100), unique=True)
    name = db.Column(db.String(100), unique=True)
    url = db.Column(db.String(400), unique=True)
    size = db.Column(db.Integer)
    flags = db.Column(db.Integer)
    installed = db.Column(db.Integer)

    def __init__(self, md5=None, name=None, url=None, size=None, flags=None, installed=None):
        self.md5 = md5
        self.name = name
        self.url = url
        self.size = size
        self.flags = flags
        self.installed = installed

# flavors database
class Flavors(CRUDMixin,  db.Model):
    __tablename__ = 'flavors'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)
    comment = db.Column(db.String(200), unique=True)
    vpu = db.Column(db.Integer)
    mem = db.Column(db.Integer)
    disk = db.Column(db.Integer)
    flags = db.Column(db.Integer)
    installed = db.Column(db.Integer)

    def __init__(self, name=None, comment=None, vpu=None, mem=None, disk=None, flags=None, installed=None):
        self.name = name
        self.comment = comment
        self.vpu = vpu
        self.mem = mem
        self.disk = disk
        self.flags = flags
        self.installed = installed