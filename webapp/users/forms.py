from flask.ext.wtf import Form, fields, validators
from wtforms import TextField, PasswordField, BooleanField
from wtforms.validators import Required, Email, EqualTo
from webapp.users.models import User
from webapp import db, bcrypt

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