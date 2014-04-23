import os
import sys
import string
import random
import json
import socket
import time
import hmac
import hashlib

from urllib2 import urlopen, HTTPError, Request, build_opener
from urllib import quote
from OpenSSL import SSL

from webapp import app
from webapp.libs.exceptions import CoinBaseAddressBuild

def row2dict(row):
	d = {}
	for column in row.__table__.columns:
		d[column.name] = getattr(row, column.name)

	return d

# download images, store locally in static/images & update images db
# NOTE: this is a blocking call, and for use from ./manage.py only
def download_images(appliance, images):
	# image path for this appliance
	image_path = "%s/../static/images" % os.path.dirname(os.path.abspath(__file__))
		
	# loop through images and try to download and install
	for image in images:
		# backup the original url
		original_url = image.url

		try:
			# connect to remote URL's site and get size
			site = urlopen(image.url)
			meta = site.info()
			size = int(meta.getheaders("Content-Length")[0])
	
			# build filename
			filename = image.url.split('/')[-1]

			# check if we have a file that size/name already
			try:
				on_disk_size = int(os.stat("%s/%s" % (image_path, filename)).st_size)
			except:
				on_disk_size = 0

			# if local disk size not equal to remote size, download it
			# TODO: this should be optimized to verify file integrity
			if on_disk_size != int(size):				
				# mark image as installing
				image.active = 2
				image.update()

				# open filename for binary write
				f = open("%s/%s" % (image_path, filename), 'wb')
				
				# write file to disk
				f.write(site.read())
				site.close()
				f.close()
				
				# update the database saying we have the file
				image.size = size
				image.active = 3

				# write the new URL for the image
				if app.config['DEBUG'] == True:
					image.url = "http://%s:%s/images/%s" % (
						appliance.local_ip, 
						app.config['DEV_PORT'],
						filename
					)
				else:
					image.url = "http://%s/images/%s" % (
						appliance.local_ip,
						filename
					)

				image.update()

			else:
				# do nothing if we already have it locally
				image.size = on_disk_size
				image.active = 3
				image.update()

		except Exception, e:
			# reset the URL so OpenStack can download it directly
			image.url = original_url
			image.active = 1
			image.update()

# uninstall downloaded images
def uninstall_image(image):
	# image path for this appliance
	image_path = "%s/../static/images" % os.path.dirname(os.path.abspath(__file__))

	# grab existing url and extract filename
	url = image.url
	filename = image.url.split('/')[-1]

	# look for file and size
	try:
		if os.path.isfile("%s/%s" % (image_path, filename)):
			# delete the image
			os.remove("%s/%s" % (image_path, filename))
			return True
	except:
		return False

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

# remote connection to pool operator's api
def server_connect(method="authorization", apitoken="unauthorized"):
	# url = app.config['APP_WEBSITE'] + '/api/v1/%s?ver=' % method + app.config['VERSION'] + '&apitoken=' + apitoken
	url = app.config['POOL_APPSPOT_WEBSITE'] + '/api/v1/%s?ver=' % method + app.config['VERSION'] + '&apitoken=' + apitoken

	response = {"response": "success", "result": ""}

	try:
		response = json.loads(urlopen(url, timeout=10).read())
	except HTTPError, e:
		response['response'] = "fail"
		response['result'] = "Error code %s returned from server. Authorization failed." % str(e.code)
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

# get the formatted decimal price of a satoshi to currency
def coinbase_get_quote(appliance=None, currency=None):
	response = {"response": "success", "result": {}}
	url = "https://coinbase.com/api/v1/currencies/exchange_rates"

	try:
		result = json.loads(urlopen(url, timeout=10).read())
		response['result'] = {currency: result[currency]}
	except IOError as ex:
		response['response'] = "fail"
		response['result'] = "Can't contact quote server.  Try again later."
	except ValueError as ex:
		response['response'] = "fail"
		response['result'] = "Having issues parsing JSON from the site: %s.  Open a ticket." % type(ex).__name__
	except Exception as ex:
		response['response'] = "fail"
		response['result'] = "An error of type %s has occured.  Open a ticket." % type(ex).__name__

	return response

# HMAC construction and Coinbase query
def coinbase_generate_address(appliance=None, callback_url=None, label=None):
	url = "https://coinbase.com/api/v1/account/generate_receive_address"
	
	# create urlib2 opener and a nonce for the session
	opener = build_opener()
	nonce = int(time.time() * 1e6)

	# massage data to fit coinbase's use of parameterized dicts
	data = "address[callback_url]=%s&address[label]=%s" % (quote(callback_url), label)

	# create and sign the message
	message = str(nonce) + url + ('' if data is None else data)
	signature = hmac.new(str(appliance.cbapisecret), message, hashlib.sha256).hexdigest()

	# pop parameters into the headers
	opener.addheaders = [('ACCESS_KEY', appliance.cbapikey),
					   ('ACCESS_SIGNATURE', signature),
					   ('ACCESS_NONCE', nonce)]

	# initialize response object
	response = {"response": "success", "result": {}}

	# call coinbase
	try:
		result = json.loads(opener.open(Request(url, data)).read())

		# check the returned data matches what we sent - adding "instance-" to the label check
		if result['callback_url'] != callback_url or result['label'] != "instance-%s" % label:
			raise CoinBaseAddressBuild("Coinbase returned mismatched parameters for callback url or label.")
		
		response['result']['address'] = result['address']

	except HTTPError as ex:
		response['response'] = "fail"
		response['result'] = "An error of type %s has occured.  Open a ticket." % type(ex).__name__
	except CoinBaseAddressBuild as ex:
		response['response'] = "fail"
		response['result'] = str(ex)
	
	return response

# HMAC construction and Coinbase query for all account addresses
def coinbase_get_addresses(appliance=None):
	url = "https://coinbase.com/api/v1/addresses?limit=1000"
	
	# create urlib2 opener and a nonce for the session
	opener = build_opener()
	nonce = int(time.time() * 1e6)

	# initialize response object
	response = {"response": "success", "result": {}}

	# create and sign the message
	message = str(nonce) + url
	signature = hmac.new(str(appliance.cbapisecret), message, hashlib.sha256).hexdigest()

	# pop parameters into the headers
	opener.addheaders = [('ACCESS_KEY', appliance.cbapikey),
					   ('ACCESS_SIGNATURE', signature),
					   ('ACCESS_NONCE', nonce)]

	# call coinbase
	try:
		result = json.loads(opener.open(Request(url)).read())
		response['result']['addresses'] = result['addresses']

	except HTTPError as ex:
		response['response'] = "fail"
		response['result'] = "An error of type %s has occured.  Open a ticket." % type(ex).__name__
	except CoinBaseAddressBuild as ex:
		response['response'] = "fail"
		response['result'] = str(ex)
	
	return response

# HMAC construction and Coinbase check
def coinbase_check(appliance=None):
	url = "https://coinbase.com/api/v1/authorization"
	
	# create urlib2 opener and a nonce for the session
	opener = build_opener()
	nonce = int(time.time() * 1e6)

	# create and sign the message
	message = str(nonce) + url
	signature = hmac.new(str(appliance.cbapisecret), message, hashlib.sha256).hexdigest()

	# pop parameters into the headers
	opener.addheaders = [('ACCESS_KEY', appliance.cbapikey),
					   ('ACCESS_SIGNATURE', signature),
					   ('ACCESS_NONCE', nonce)]

	# call coinbase
	try:
		result = json.loads(opener.open(Request(url)).read())
		return True
	except:
		return False

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

