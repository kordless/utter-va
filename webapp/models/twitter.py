import time

from webapp import app
from webapp import db

from webapp.models.mixins import CRUDMixin

from webapp.models.images import Images
from webapp.models.flavors import Flavors
from webapp.models.instances import Instances

# twitter bot model
class TwitterBot(CRUDMixin, db.Model):
	__tablename__ = 'twitterbot'
	id = db.Column(db.Integer, primary_key=True)
	screen_name = db.Column(db.String(100))
	oauth_url = db.Column(db.String(400))
	oauth_token = db.Column(db.String(100))
	oauth_token_secret = db.Column(db.String(100))
	consumer_key = db.Column(db.String(100))
	consumer_secret = db.Column(db.String(100))
	complete = db.Column(db.Integer)
	enabled = db.Column(db.Integer)
	flavor_id = db.Column(db.Integer, db.ForeignKey('flavors.id'))
	max_instances = db.Column(db.Integer)
	announce = db.Column(db.Integer)
	updated = db.Column(db.Integer)

	# relationships
	flavor = db.relationship('Flavors', foreign_keys='TwitterBot.flavor_id')

	def __init__(
		self,
		screen_name=None,
		oauth_url=None,
		oauth_token=None,
		oauth_token_secret=None,
		consumer_key=None,
		consumer_secret=None,
		complete=None,
		enabled=None,
		flavor_id=None,
		max_instances=None,
		announce=None,
		updated=None
	):
		self.screen_name = screen_name
		self.oauth_url = oauth_url
		self.oauth_token = oauth_token
		self.oauth_token_secret = oauth_token_secret
		self.consumer_key = consumer_key
		self.consumer_secret = consumer_secret
		self.complete = complete
		self.enabled = enabled
		flavor_id = flavor_id
		max_instances = max_instances
		announce = announce
		updated = updated

# tweet commands model
class TweetCommands(CRUDMixin, db.Model):
	__tablename__ = 'tweetcommands'
	id = db.Column(db.Integer, primary_key=True)
	created = db.Column(db.Integer)	
	updated = db.Column(db.Integer)
	user = db.Column(db.String(100))
	command = db.Column(db.String(100))
	url = db.Column(db.String(400))
	instance_id = db.Column(db.Integer, db.ForeignKey('instances.id'))
	state = db.Column(db.Integer)

	# relationships
	instance = db.relationship('Instances', foreign_keys='TweetCommands.instance_id')

	def __init__(
		self,
		created=None,
		updated=None,
		user=None,
		command=None,
		url=None,
		instance_id=None,
		state=None
	):
		self.created = created
		self.updated = updated
		self.user = user
		self.command = command
		self.url = url
		self.instance_id = instance_id
		self.state = state
