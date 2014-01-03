from datetime import datetime
 
from flask import *
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from werkzeug import generate_password_hash, check_password_hash
 
from webapp import app
from webapp.database import Base

# Standard Databases
class User(Base):
    __tablename__ = 'users'
    uid = Column(Integer, primary_key=True)
    username = Column(String(60))
    pwdhash = Column(String())
    email = Column(String(60))
    activate = Column(Boolean)
    created = Column(DateTime)
 
    def __init__(self, username, password, email):
        self.username = username
        self.pwdhash = generate_password_hash(password)
        self.email = email
        self.activate = False
        self.created = datetime.utcnow()
 
    def check_password(self, password):
        return check_password_hash(self.pwdhash, password)
