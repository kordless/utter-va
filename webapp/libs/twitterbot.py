# -*- coding: utf-8 -*-
import time
import re
import sys

from urlparse import urlparse

from webapp import app, db

from webapp.models.twitter import TwitterBot, TweetCommands
from webapp.models.instances import Instances
from webapp.models.flavors import Flavors

from webapp.libs.twitter.api import Twitter
from webapp.libs.twitter.stream import TwitterStream
from webapp.libs.twitter.oauth import OAuth
from webapp.libs.utils import message

def parse_oauth_tokens(result):
	screen_name = ""
	for r in result.split('&'):
		k, v = r.split('=')
		if k == 'oauth_token':
			oauth_token = v
		elif k == 'oauth_token_secret':
			oauth_token_secret = v
		elif k == 'screen_name':
			screen_name = v
	return oauth_token, oauth_token_secret, screen_name

# '!instance' command handling
def reserve_instance(command, bot):
	# default response
	response = {"response": "success", "result": {"message": ""}}

	# check quota
	if int(db.session.query(TweetCommands).filter_by(command="instance").count()) >= bot.max_instances:
		tweet_status("Sorry @%s, I'm at my %s instance quota. Wait a bit and try again." % (user, bot.max_instances))
		command.delete(command)
		response['response'], response['result'] = "error", "Instance quota reached."
		return response

	# check the user doesn't have another instance already
	ic = db.session.query(TweetCommands).filter_by(command="instance", user=command.user).count()
	if ic > 1:
		tweet_status("Sorry, I only do %s instance(s) per user." % 1, command.user)
		command.delete(command)
		response['response'], response['result'] = "error", "User limit encountered."
		return response

	# grab a URL in the format ^http://pastebin.com/raw.php?i=n1p4BU40
	test = urlparse(command.url)
	
	# test if we have a good protocol and location - REFACTOR
	if not test.netloc:
		tweet_status("I need a valid instance command which includes a ! before the command and a ^ before a valid URL.", user) 
		response['response'], response['result'] = "error", "Missing URL in instance command."
		return response

	# grab an instance to reserve
	instance = Instances()
	response = instance.reserve(command.url, bot.flavor_id)

	# notify the console
	message(response['result']['message'], response['response'], True)

	# return errors, if any
	if response['response'] == "error":
		return response

	# update the command to reflect the new instance status
	instance = response['result']['instance']
	command.state = 10
	command.updated = int(time.time())
	command.instance_id = instance['id']
	command.update()
	
	# pack command into response
	response['result']['command'] = command

	# tweet bits
	ask = "%0.6f" % (float(response['result']['ask'])/1000000)
	address = response['result']['address']
	name = instance['name']
	
	# tell the user the bitcoin address
	tweet = "send %s BTC/hour to https://blockchain.info/address/%s in next 5 mins to start ~%s." % (ask, address, name)
	tweet_status(tweet, command.user)

	return response

# '!status' command handling
def run_status(command, bot):
	# default response
	response = {"response": "success", "result": {"message": ""}}

	# if instance is set, we use it
	if command.instance:
		if command.instance.state == 10:
			# tweet bits
			ask = "%0.6f" % (float(command.instance.flavor.ask)/1000000)
			address = command.instance.address.address
			name = command.instance.name

			# haven't paid for it, silly gooses
			tweet = "send %s BTC/hour to https://blockchain.info/address/%s to start ~%s." % (ask, address, name)
			tweet_status(tweet, command.user)

			response['result']['message'] = "Sent payment reminder."

		elif command.instance.message:
			# we have an error message, so send it out
			name = command.instance.name
			message = command.instance.message
			tweet = "Instance ~%s error. Pennies for nothing. %s" % (name, message)
			tweet_status(tweet, command.user)

		else:
			# load the instance
			instance = db.session.query(Instances).filter_by(id=command.instance_id).first()

			# is instance doing anything?
			if instance.state == 4:
				# get the time left in seconds
				epoch_time = int(time.time())
				expires = command.instance.expires
				timer = expires - epoch_time
				if timer < 0:
					timer = 0

				tweet_status("~%s | ipv6: %s | ipv4: %s | ipv4: %s | exp: %ss" % (
						command.instance.name,
						command.instance.publicipv6,
						command.instance.privateipv4,
						command.instance.publicipv4,
						timer
					),
					command.user
				)
			else:
				tweet_status("Instance ~%s is not reserved." % instance.name, command.user)

			response['result']['message'] = "Sent instance information."

	else:
		# no instance, so look up if they have an instance
		user_command = db.session.query(TweetCommands).filter_by(user=command.user, command="instance").first()
		command_count = db.session.query(TweetCommands).filter_by(command="instance").count()
		
		# remind them of the instance name
		if user_command:
			tweet = "do a '@%s !status ~%s'" % (bot.screen_name, user_command.instance.name)
			tweet_status(tweet, command.user)
			response['result']['message'] = "Sent instance status help message."

		# tweet system status
		available = int(bot.max_instances) - int(command_count)
		tweet_status("%s of %s slots available to serve %s instances." % (
				available,
				bot.max_instances,
				bot.flavor.name
			), 
			command.user
		)
		pass

		# delete the status request
		command.delete(command)

	return response

# check up on instances
def check_instance(command, bot):
	# check if command has an instance_id
	if command.instance_id == 0:
		return False

	instance = db.session.query(Instances).filter_by(id=command.instance_id).first()

	# if we couldn't find the instance, there's nothign we can do
	if not instance:
		command.delete(command)
		return False

	elif instance.message and instance.message_count > 10:
		# we have an error message, so send it out
		name = instance.name
		message = instance.message
		tweet = "Instance ~%s error. Pennies for nothing. %s" % (name, message)
		tweet_status(tweet, command.user)
		command.delete(command)
		return False

	# check if instance changed state
	if instance.state != command.state:
		# check if instance is in run state so we can tweet about it
		if instance.state == 4:
			tweet_status("~%s | ipv6: %s | ipv4: %s | ipv4: %s" %
				(
					instance.name,
					instance.publicipv6,
					instance.privateipv4,
					instance.publicipv4
				),
				command.user
			)
		elif instance.state == 7:
			# decomissioned
			command.delete(command)
	
	# now sync the states
	command.state = instance.state
	command.update()

	return True

# deletes instance reservations and old errant messages
def cleanup_reservations(command, bot):
	# check if timeout
	epoch_time = int(time.time())

	# cancel reservation if older than 7 minutes (we fudge this in the tweet)
	if (command.updated + 420) < epoch_time:
		instance = db.session.query(Instances).filter_by(id=command.instance_id).first()

		if instance:
			instance.callback_url = ""
			instance.state = 1
			instance.update()
			message("Canceled reservation on %s." % instance.name, "error", True)

		command.delete(command)


def get_stream():
	# loop forever trying to talk to twitter
	while True:
		# load and check bot settings
		bot = TwitterBot.get()
		if not bot.enabled:
			sys.exit()

		# authenticate and begin
		try:
			auth = OAuth(
				bot.oauth_token,
				bot.oauth_token_secret,
				bot.consumer_key,
				bot.consumer_secret
			)

			# establish connection
			twitter_userstream = TwitterStream(auth=auth, domain='userstream.twitter.com')
			
			# iterator provides infinite status updates
			for update in twitter_userstream.user():
				# look in the update for a text message (others include delete, friends)
				if 'text' in update:
					# skip it if it's a reply
					if update['in_reply_to_status_id']:
						continue

					# load the screen name/username
					user = update['user']['screen_name']

					# check if somebody said 'settings' and then restart
					if "!settings" in update['text']:
						sys.exit()

					# grab the command in the format !instance
					r = re.search('\!([a-zA-Z]*)', update['text'])
					try:
						command = r.group(1)
					except:
						# always need a command
						continue

					# ignore ourselves
					if user == bot.screen_name:
						continue
						
					# ditch it if it's blank
					if command == "":
						continue

					# extract a url following a ^
					try:
						r = re.search('\^(\S*)', update['text'])
						url = r.group(1)

					except:
						url = ""

					# grab an instance name in the format ~smi-avv4mtmm
					instance = None
					try:
						r = re.search('\~(\S*)', update['text'])

						# extract and lookup instance by name
						instance_name = r.group(1)
						instance = db.session.query(Instances).filter_by(name=instance_name).first()

					except:
						pass

					# write to database
					tc = TweetCommands()
					tc.created = int(time.time())
					tc.updated = int(time.time())
					tc.user = user
					tc.command = command.lower()
					tc.url = url
					
					if instance:
						tc.instance_id = instance.id
					else:
						tc.instance_id = 0

					tc.state = 1 # initialize
					tc.update()

					# send message
					message("Received a command from Twitter", "success", False)
					app.logger.info("Received a command=(%s) from Twitter." % tc.command)
				else:
					# other types of messages
					pass

		except Exception as ex:
			app.logger.error("Twitter stream disconnected.  Letting monit handle restart.")
			time.sleep(15)

	return

def tweet_status(text="Who wants to smoke some instances with me?", user=None):
	# default response
	response = {"response": "success", "result": {"message": "Tweet sent."}}

	bot = TwitterBot.get()

	try:
		twitter = Twitter(
			auth=OAuth(
				bot.oauth_token,
				bot.oauth_token_secret,
				bot.consumer_key,
				bot.consumer_secret
			)
		)

		# toggle dm or regular message based on if we got a user in the call
		if user:
			try:
				twitter.direct_messages.new(text, user=None)
			except:
				# build a fake DM cause they aren't following us
				dm = ". @%s %s" % (user, text)
				twitter.statuses.update(status=dm)
		else:
			twitter.statuses.update(status=text)
	
	except Exception as ex:
		response['response'] = "error"
		response['result']['message'] = "Something went wrong with posting.  Ensure you are running good credentials and making non-duplicate posts!"
		app.logger.error(ex)

	return response

def oauth_initialize():
	# twitter credential db
	bot = TwitterBot.get()

	if not bot:
		bot = TwitterBot()
		bot.consumer_key = app.config['CONSUMER_KEY']
		bot.consumer_secret = app.config['CONSUMER_SECRET']
		bot.complete = 0
		bot.enabled = 0
		bot.flavor_id = 0
		bot.max_instances = app.config['MAX_INSTANCES_DEFAULT']
		bot.announce = 0
		bot.updated = int(time.time())

	# give twitter a holler
	try:
		twitter = Twitter(
			auth=OAuth(
				"", 
				"", 
				bot.consumer_key, 
				bot.consumer_secret
			),
			format="", 
			api_version=None
		)

		# screen name won't be set until oauth_complete runs
		oauth_token, oauth_token_secret, screen_name = parse_oauth_tokens(
			twitter.oauth.request_token()
		)
		oauth_url = "https://api.twitter.com/oauth/authorize?oauth_token=%s" % oauth_token

	except Exception as ex:
		return bot

	# update the entries with what we got back
	bot.oauth_token = oauth_token
	bot.oauth_token_secret = oauth_token_secret
	bot.oauth_url = oauth_url
	bot.screen_name = screen_name
	bot.complete = 1
	bot.enabled = 0
	bot.flavor_id = 0
	bot.max_instances = app.config['MAX_INSTANCES_DEFAULT']
	bot.announce = 0
	bot.updated = int(time.time())
	bot.update()

	return bot

def oauth_complete(oauth_verifier):
	# twitter credential db
	bot = TwitterBot.get()

	try:
		twitter = Twitter(
			auth=OAuth(
				bot.oauth_token,
				bot.oauth_token_secret, 
				bot.consumer_key, 
				bot.consumer_secret
			),
			format='', 
			api_version=None
		)
		oauth_token, oauth_token_secret, screen_name = parse_oauth_tokens(
			twitter.oauth.access_token(oauth_verifier=oauth_verifier)
		)
	except Exception as ex:
		return bot

	# twitter credential db
	bot = TwitterBot.get()
	
	# get a flavor we can use for default
	flavor = db.session.query(Flavors).order_by().first()

	# update the entry
	bot.screen_name = screen_name
	bot.oauth_url = "" # becomes invalid
	bot.oauth_token = oauth_token
	bot.oauth_token_secret = oauth_token_secret
	bot.complete = 2
	bot.enabled = 1
	bot.flavor_id = flavor.id
	bot.max_instances = app.config['MAX_INSTANCES_DEFAULT']
	bot.announce = 0
	bot.updated = int(time.time())
	bot.update()

	return bot

