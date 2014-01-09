from webapp import db, bcrypt
from webapp.mixins import CRUDMixin
from flask.ext.login import UserMixin
from werkzeug import generate_password_hash, check_password_hash

# user database
class User(UserMixin, CRUDMixin,  db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(100), unique=True)
    email = db.Column(db.String(100))
    accountid = db.Column(db.String(32))
 
    def __init__(self, username=None, password=None):
        self.username = username
        self.password = password

    def __repr__(self):
        return '<Username %r>' % (self.username)