import sys
import string
import random
import socket

from urllib2 import urlopen
from urllib import quote_plus
from webapp import app

def row2dict(row):
	d = {}
	for column in row.__table__.columns:
		d[column.name] = getattr(row, column.name)

	return d

# nicely formatted tables
# http://stackoverflow.com/questions/5909873/python-pretty-printing-ascii-tables
def pprinttable(rows):
	if len(rows) > 1:
		headers = rows[0]._fields
		lens = []
	
		for i in range(len(rows[0])):
			lens.append(len(max([x[i] for x in rows] + [headers[i]],key=lambda x:len(str(x)))))
		
		formats = []
		hformats = []
		
		for i in range(len(rows[0])):
			if isinstance(rows[0][i], int):
				formats.append("%%%dd" % lens[i])
			else:
				formats.append("%%-%ds" % lens[i])
			hformats.append("%%-%ds" % lens[i])
		
		pattern = " | ".join(formats)
		hpattern = " | ".join(hformats)
		separator = "-+-".join(['-' * n for n in lens])
		
		print hpattern % tuple(headers)
		print separator
		
		for line in rows:
			print pattern % tuple(line)
  	
  	elif len(rows) == 1:
		row = rows[0]
		hwidth = len(max(row._fields,key=lambda x: len(x)))
		for i in range(len(row)):
			print "%*s = %s" % (hwidth,row._fields[i],row[i])

# yes or no question handler
def query_yes_no(question, default="no"):
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
			sys.stdout.write("Please respond with 'yes' or 'no' (or 'y' or 'n').\n")

def generate_token(size=64, caselimit=False):
	if caselimit:
		characters  = string.ascii_lowercase + string.digits
	else:
		characters  = string.ascii_uppercase + string.ascii_lowercase + string.digits
	token = ''.join(random.choice(characters) for x in range(size))
	return token
	
# message bus - sending messages to ourselves
def message(text=None, status="success", reloader=False):
	from webapp.models.models import Appliance
	apitoken = Appliance().get().apitoken

	# muck reloader string
	reloader = "true" if reloader else "false"

	if app.config['DEBUG'] == True:
		url = "http://0.0.0.0:%s/api/message?text=%s&status=%s&reload=%s&apitoken=%s" % (
			app.config['DEV_PORT'],
			quote_plus(text),
			status,
			reloader,
			apitoken
		)
	else:
		url = "http://0.0.0.0:80/api/message?text=%s&status=%s&reload=%s&apitoken=%s" % (
			quote_plus(text),
			status,
			reloader,
			apitoken
		)

	try:
		response = urlopen(url, data="", timeout=10).read()
		return True
	except Exception, e:
		return False

# check ngrok is up on port 4040
def ngrok_checker(appliance=None):
	# use the local port 5000 to test if we're running in debug
	if app.config['DEBUG'] == True:
		url = "http://127.0.0.1:5000/"
	else:
		url = "https://%s.ngrok.com/" % appliance.subdomain

	try:
		response = urlopen(url, timeout=10).read()

		if appliance.ngroktoken == "" or not appliance.ngroktoken:
			return 0
		else:
			return 1
	except Exception, e:
		return -1
