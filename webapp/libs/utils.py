import sys
import string
import random
import json
import socket

from urllib2 import urlopen, HTTPError
from OpenSSL import SSL

from webapp import app

def row2dict(row):
	d = {}
	for column in row.__table__.columns:
		d[column.name] = getattr(row, column.name)

	return d

def query_yes_no(question, default="no"):
	"""Ask a yes/no question via raw_input() and return their answer.

	"question" is a string that is presented to the user.
	"default" is the presumed answer if the user just hits <Enter>.
		It must be "yes" (the default), "no" or None (meaning
		an answer is required of the user).

	The "answer" return value is one of "yes" or "no".
	"""
	valid = { "yes":True, "y":True, "ye":True, "no":False, "n":False}
	if default == None:
		prompt = " [y/n] "
	elif default == "yes":
		prompt = " [Y/n] "
	elif default == "no":
		prompt = " [y/N] "
	else:
		raise ValueError("invalid default answer: '%s'" % default)

	while True:
		sys.stdout.write(question + prompt)
		choice = raw_input().lower()
		if default is not None and choice == '':
			return valid[default]
		elif choice in valid:
			return valid[choice]
		else:
			sys.stdout.write("Please respond with 'yes' or 'no' "\
							 "(or 'y' or 'n').\n")

def configure_blurb():
	hostname = socket.gethostname()
	IP = socket.gethostbyname(hostname)
	print "Visit http://%s/ to setup your appliance." % IP

def generate_token(size=64, caselimit=False):
	if caselimit:
		characters  = string.ascii_lowercase + string.digits
	else:
		characters  = string.ascii_uppercase + string.ascii_lowercase + string.digits
	token = ''.join(random.choice(characters) for x in range(size))
	return token

# remote connection to pool operator
def server_connect(method="version", apitoken=None):
	url = app.config['APP_WEBSITE'] + '/api/%s?ver=' % method + app.config['VERSION'] + '&apitoken=' + apitoken

	response = {"response": "success", "result": ""}

	try:
		result = urlopen(url, timeout=10).read()
		response['result'] = json.loads(result)
	except IOError as ex:
		response['response'] = "fail"
		response['result'] = "Can't contact pool server.  Try again later."
	except ValueError as ex:
		response['response'] = "fail"
		response['result'] = "Having issues parsing JSON from the site: %s.  Open a ticket." % type(ex).__name__
	except Exception as ex:
		response['response'] = "fail"
		response['result'] = "An error of type %s has occured.  Open a ticket." % type(ex).__name__

	return response

