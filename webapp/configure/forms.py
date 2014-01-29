from flask.ext.wtf import Form, fields, validators
from wtforms import TextField, PasswordField, IntegerField, DecimalField, ValidationError
from wtforms.validators import Required, Email, EqualTo
from webapp.configure.models import OpenStack, Appliance
from webapp.api.models import Instances
from webapp.libs.utils import blockchain_validate
from webapp import db

class OpenStackForm(Form):
	authurl = TextField(validators=[Required()])
	tenantname = TextField(validators=[Required()])
	tenantid = TextField(validators=[Required()])
	osusername = TextField(validators=[Required()])
	ospassword = PasswordField(validators=[Required()])

	def get_openstack(self):
		return db.session.query(OpenStack).first()

def paymentaddress_validate(form, field):
	result = blockchain_validate(field.data)
	if result['response'] == "fail":
		raise ValidationError("Invalid checksum for payment address '%s'." % field.data)

class ApplianceForm(Form):
	paymentaddress = TextField(validators=[Required(), paymentaddress_validate])
	apitoken = TextField()
	ngroktoken = TextField()
	serviceurl = TextField()
	latitude = TextField(validators=[Required()])
	longitude = TextField(validators=[Required()])

	def get_appliance(self):
		return db.session.query(Appliance).first()

class InstanceForm(Form):
	created = IntegerField()
	updated = IntegerField() 
	expires = IntegerField()
	osflavorid = TextField(validators=[Required()])
	osimageid = TextField(validators=[Required()])
	publicip = TextField()
	ssltunnel = TextField()
	instanceid = TextField()
	name = TextField(validators=[Required()])
	state = IntegerField()
	secret = TextField()
	confirmations = IntegerField()
	callbackurl = TextField()
	feepercent = DecimalField()
	destination = TextField()
	inputaddress = TextField()
	transactionhash = TextField()

	def get_instance(self):
		return db.session.query(Instance).first()