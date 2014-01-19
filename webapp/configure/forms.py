from flask.ext.wtf import Form, fields, validators
from wtforms import TextField, PasswordField, BooleanField
from wtforms.validators import Required, Email, EqualTo
from webapp.configure.models import OpenStack, Appliance
from webapp import db

class OpenStackForm(Form):
	authurl = TextField(validators=[Required()])
	tenantname = TextField(validators=[Required()])
	tenantid = TextField(validators=[Required()])
	osusername = TextField(validators=[Required()])
	ospassword = PasswordField(validators=[Required()])

	def get_openstack(self):
		return db.session.query(OpenStack).first()


class ApplianceForm(Form):
	apitoken = TextField(validators=[Required()])
	ngroktoken = TextField(validators=[Required()])
	serviceurl = TextField(validators=[Required()])
	latitude = TextField(validators=[Required()])
	longitude = TextField(validators=[Required()])

	def get_appliance(self):
		return db.session.query(Appliance).first()