from flask.ext.wtf import Form, fields, validators
from wtforms import TextField, PasswordField, BooleanField, IntegerField, DecimalField, ValidationError
from wtforms.validators import Required, Email, EqualTo

from webapp import db, bcrypt

from webapp.models.models import User

def validate_login(form, field):
	user = form.get_user()

	if user is None:
		raise validators.ValidationError('Invalid user.')

	if not bcrypt.check_password_hash(user.password, form.password.data):
		raise validators.ValidationError('Login failed, yo.')


class LoginForm(Form):
	username = TextField(validators=[Required()])
	password = PasswordField(validators=[Required(), validate_login])

	def get_user(self):
		return db.session.query(User).filter_by(username=self.username.data).first()


class RegisterForm(Form):
	username = TextField(validators=[Required()])
	password = PasswordField(validators=[Required(), EqualTo('conf_password', message="Passwords don't match.")])
	conf_password = PasswordField(validators=[Required()])


class OpenStackForm(Form):
	authurl = TextField("Authentication URL", validators=[Required()])
	tenantname = TextField("Tenant Name", validators=[Required()])
	tenantid = TextField("Tenant ID", validators=[Required()])
	osusername = TextField("OpenStack Username", validators=[Required()])
	ospassword = PasswordField("OpenStack Password", validators=[Required()])


class ApplianceForm(Form):
	cbapikey = TextField("Coinbase Client ID", validators=[Required()])
	cbapisecret = TextField("Coinbase Client Secret", validators=[Required()])
	apitoken = TextField("Pool API Token") # not submitted by form
	ngroktoken = TextField("Ngrok Token", validators=[Required("The SSL Tunnel Token is required.")])
	latitude = TextField("latitude", validators=[Required()])
	longitude = TextField("longitude", validators=[Required()])


class InstanceForm(Form):
	name = TextField(validators=[Required()])
	osflavorid = TextField(validators=[Required()])
	osimageid = TextField(validators=[Required()])
	hourlyrate = IntegerField(validators=[Required()])