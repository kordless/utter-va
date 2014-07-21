# -*- coding: utf-8 -*-
import time
import re
import sys

from urlparse import urlparse

from webapp import app, db

from webapp.models.twitter import TwitterBot, TweetCommands
from webapp.models.instances import Instances

from webapp.libs.twitter.api import Twitter
from webapp.libs.twitter.stream import TwitterStream
from webapp.libs.twitter.oauth import OAuth
from webapp.libs.utils import message

def parse_oauth_tokens(result):
	for r in result.split('&'):
		k, v = r.split('=')
		if k == 'oauth_token':
			oauth_token = v
		elif k == 'oauth_token_secret':
			oauth_token_secret = v
	return oauth_token, oauth_token_secret

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

					# ensure we are saying 'settings' and then restart
					if user.lower() == "obitcoin":
						if "settings" in update['text']:
							sys.exit()
						continue

					# grab the command in the format !instance
					r = re.search('\!(\S*)', update['text'])
					try:
						command = r.group(1)
					except:
						# always need a command
						continue

					# grab a URL in the format ^http://pastebin.com/raw.php?i=n1p4BU40
					error_message = "I need a valid instance command which includes a ! before the command and a ^ before a valid URL." 
					
					try:
						r = re.search('\^(\S*)', update['text'])
						url = r.group(1)
						test = urlparse(url)

						# test if we have a good protocol and location - REFACTOR
						if not test.netloc:
							if command.lower() == "instance":
								tweet_status(error_message, user)
							continue

					except:
						if command.lower() == "instance":
							tweet_status(error_message, user)
							continue
						else:
							url = ""

					# skip this instance command if we are over instance quota
					if command.lower() == "instance":
						if int(db.session.query(TweetCommands).filter_by(command="instance").count()) >= bot.max_instances:
							tweet_status("Sorry @%s, I'm at my %s instance quota. Wait a bit and try again." % (user, bot.max_instances))
							continue

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
					message("Received a message from Twitter.", "success", False)

				else:
					# other types of messages
					pass

		except Exception as ex:
			print str(ex)
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
		response['response'] = "fail"
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
		bot.update()

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
		oauth_token, oauth_token_secret = parse_oauth_tokens(
			twitter.oauth.request_token()
		)
		oauth_url = "https://api.twitter.com/oauth/authorize?oauth_token=%s" % oauth_token

	except:
		return False

	# update the entries with what we got back
	bot.oauth_token = oauth_token
	bot.oauth_token_secret = oauth_token_secret
	bot.oauth_url = oauth_url
	bot.complete = 1
	bot.enabled = 0
	bot.flavor_id = 0
	bot.max_instances = app.config['MAX_INSTANCES_DEFAULT']
	bot.announce = 0
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
		oauth_token, oauth_token_secret = parse_oauth_tokens(
			twitter.oauth.access_token(oauth_verifier=oauth_verifier)
		)

	except:
		return False

	# twitter credential db
	bot = TwitterBot.get()
	
	# update the entry
	bot.oauth_url = "" # becomes invalid
	bot.oauth_token = oauth_token
	bot.oauth_token_secret = oauth_token_secret
	bot.complete = 2
	bot.enabled = 1
	bot.flavor_id = 0
	bot.max_instances = app.config['MAX_INSTANCES_DEFAULT']
	bot.announce = 1
	bot.update()

	return bot

