from flask import Blueprint, render_template, flash, redirect, session, url_for, request, g
from flask.ext.login import login_user, logout_user, current_user, login_required
from webapp import app, db, bcrypt, login_manager
from forms import LoginForm, RegisterForm
from webapp.users.models import User

mod = Blueprint('users', __name__)

# user login callback
@login_manager.user_loader
def load_user(user_id):
	return User.query.get(int(user_id))

# home page
@mod.route('/login', methods=['GET', 'POST'])
def login():
	# if user is already logged in go to status
	if current_user.is_authenticated():
		return redirect(url_for("configure.configure"))

	# if there are no users in the db redirect to register
	if not db.session.query(User).first():
		return redirect(url_for('.register'))

	# load form and check login
	form = LoginForm(request.form)
	if form.validate_on_submit():
		user = form.get_user()
		login_user(user)
		return redirect(request.args.get("next") or url_for("index"))
	
	return render_template('users/login.html', form=form)

# logout route
@mod.route('/logout')
@login_required
def logout():
	logout_user()
	return redirect(url_for('index'))

# register user
@mod.route('/register', methods=['GET', 'POST'])
def register():
	# register our form
	form = RegisterForm(request.form)

	# check to see if a user is already registered in db
	# if user/pass pair is lost/forgotten use resetdb.sh
	if db.session.query(User).first():
		return redirect(url_for('.login'))

	# if we have a valid form, handle registration
	if form.validate_on_submit():
		user = User()
		form.populate_obj(user)
		user.password = bcrypt.generate_password_hash(user.password)
		db.session.add(user)
		db.session.commit()
		login_user(user)
		return redirect(url_for("configure.configure"))
	
	return render_template("users/register.html", form=form)