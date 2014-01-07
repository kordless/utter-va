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
@mod.route('/login/', methods=('GET', 'POST'))
def login_view():
	form = LoginForm(request.form)
	if form.validate_on_submit():
		user = form.get_user()
		login_user(user)
		return redirect(request.args.get("next") or url_for("index"))
	return render_template('users/login.html', form=form)

# logout route
@login_required
@mod.route('/logout/')
def logout_view():
	logout_user()
	return redirect(url_for('index'))

# getting started page
@mod.route('/register/', methods=['GET', 'POST'])
def register():
	# check to see if user already exists
	if db.session.query(User).first():
		print "found a user"
	form = RegisterForm(request.form)
	if form.validate_on_submit():
		# check to see if a user already exists - TODO
		if False:
			# bounce back to main page
			flash("User already exists.")
			return redirect(url_for("index"))
		else:
			user = User()
			form.populate_obj(user)
			user.password = bcrypt.generate_password_hash(user.password)
			db.session.add(user)
			db.session.commit()
			login_user(user)
			flash("logged in")
			return redirect(request.args.get("next") or url_for("index"))
	
	return render_template("users/register.html", form=form)