from flask.ext.wtf import Form, fields, validators
from wtforms import TextField, PasswordField, IntegerField, DecimalField, ValidationError
from wtforms.validators import Required

from webapp import db
from webapp.libs.blockchain import blockchain_validate

class OpenStackForm(Form):
	authurl = TextField(validators=[Required()])
	tenantname = TextField(validators=[Required()])
	tenantid = TextField(validators=[Required()])
	osusername = TextField(validators=[Required()])
	ospassword = PasswordField(validators=[Required()])


class ApplianceForm(Form):
	cbapikey = TextField("Coinbase Client ID", validators=[Required()])
	cbapisecret = TextField("Coinbase Client Secret", validators=[Required()])
	apitoken = TextField("Pool API Token") # not submitted by form
	ngroktoken = TextField("Ngrok Token", validators=[Required("The SSL Tunnel Token is required.")])
	latitude = TextField("latitude", validators=[Required()])
	longitude = TextField("longitude", validators=[Required()])

# instance model is located in the API directory
class InstanceForm(Form):
	name = TextField(validators=[Required()])
	osflavorid = TextField(validators=[Required()])
	osimageid = TextField(validators=[Required()])
	hourlyrate = IntegerField(validators=[Required()])