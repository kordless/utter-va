import sys
import string
import random
import socket

from urllib2 import urlopen
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

# check ngrok is up on port 4040
def ngrok_check(appliance=None):
	# use the local port 4040 to test if we're running in debug
	if app.config['DEBUG'] == True:
		url = "http://127.0.0.1:4040/"
	else:
		url = "https://%s.ngrok.com/" % appliance.subdomain

	try:
		response = urlopen(url, timeout=10).read()
		return True
	except Exception, e:
		return False

