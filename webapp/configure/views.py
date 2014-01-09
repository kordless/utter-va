from flask import Blueprint, render_template, flash, redirect, session, url_for, request, g
from flask.ext.login import login_user, logout_user, current_user, login_required
from webapp import app, db, bcrypt, login_manager
# from forms import LoginForm, RegisterForm
from webapp.users.models import User

mod = Blueprint('configure', __name__)

# user login callback
@login_manager.user_loader
def load_user(user_id):
	return User.query.get(int(user_id))

ALLOWED_EXTENSIONS = set(['sh'])
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

# configuration pages
@mod.route('/configure/', methods=('GET', 'POST'))
@login_required
def configure():
	form = False
	return render_template('configure/appliance.html', form=form)

@mod.route('/configure/openstack/', methods=('GET', 'POST'))
@login_required
def configure_openstack():
	if request.method == 'POST':
		file = request.files['file']
		if file and allowed_file(file.filename):
			print file.read()
		elif file:
			flash("File type not allowed or empty.  Try again.")

	form = False
	return render_template('configure/openstack.html', form=form)	

@mod.route('/configure/instances/', methods=('GET', 'POST'))
@login_required
def configure_instances():
	print current_user
	form = False
	return render_template('configure/instances.html', form=form)