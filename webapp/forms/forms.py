from flask.ext.wtf import Form, fields, validators
from wtforms import TextField, PasswordField, BooleanField, IntegerField, DecimalField, SelectField, ValidationError
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
	username = TextField("Username", validators=[Required()])
	password = PasswordField("Password", validators=[Required(), validate_login])

	def get_user(self):
		return db.session.query(User).filter_by(username=self.username.data).first()


class RegisterForm(Form):
	username = TextField("Username", validators=[Required()])
	password = PasswordField("Password", validators=[Required(), EqualTo('conf_password', message="Passwords don't match.")])
	conf_password = PasswordField("Password Again", validators=[Required()])


class OpenStackForm(Form):
	authurl = TextField("Authentication URL", validators=[Required()])
	tenantname = TextField("Tenant Name", validators=[Required()])
	tenantid = TextField("Tenant ID", validators=[Required()])
	osusername = TextField("OpenStack Username", validators=[Required()])
	ospassword = PasswordField("OpenStack Password", validators=[Required()])


class ApplianceForm(Form):
	cbapikey = TextField("Coinbase Client ID", validators=[])
	cbapisecret = TextField("Coinbase Client Secret", validators=[])
	apitoken = TextField("Pool API Token") # not submitted by form
	ngroktoken = TextField("Ngrok Token", validators=[])
	latitude = TextField("latitude", validators=[Required()])
	longitude = TextField("longitude", validators=[Required()])


class TwitterForm(Form):
	pin = IntegerField("Twitter Pin", validators=[Required()])


class BotForm(Form):
	flavor = SelectField("Flavor to Market", coerce=int, choices=[])
	max_instances = IntegerField("Max Instances to Advertise", validators=[Required()])
	announce = SelectField("Announce Offering", coerce=int, choices=[(0, "None"),(6, "Every 6 Hours"),(24, "Daily")])

