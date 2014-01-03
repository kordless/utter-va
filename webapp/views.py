from webapp import app
from flask import render_template
from flask.ext.login import LoginManager
from flask.ext.openid import OpenID

from webapp import models

lm = LoginManager()
lm.init_app(app)

@app.route('/')
def index():
    return render_template('home.html')
