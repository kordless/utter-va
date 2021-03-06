import time
import json
import hmac
import hashlib

from urllib2 import urlopen, Request, build_opener, HTTPError
from urllib import quote

# address build exception
class AddressBuild(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return repr(self.value)

# HMAC construction and Coinbase query
def blockchain_generate_address(appliance=None, callback_url=None, label=None):
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
		result = json.loads(opener.open(Request(url, data), timeout=10).read())

		# check the returned data matches what we sent - adding "instance-" to the label check
		if result['callback_url'] != callback_url or result['label'] != label:
			raise CoinBaseAddressBuild("Coinbase returned mismatched parameters for callback url or label.")
		
		response['result']['address'] = result['address']

	except HTTPError as ex:
		response['response'] = "error"
		response['result'] = "An error of type %s has occured.  Open a ticket." % type(ex).__name__
	except AddressBuild as ex:
		response['response'] = "error"
		response['result'] = str(ex)
	
	return response

# HMAC construction and Coinbase query for all account addresses
def blockchain_get_addresses(appliance=None):
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
		result = json.loads(opener.open(Request(url), timeout=10).read())
		response['result']['addresses'] = result['addresses']

	except HTTPError as ex:
		response['response'] = "error"
		response['result'] = "An error of type %s has occured.  Open a ticket." % type(ex).__name__
	except CoinBaseAddressBuild as ex:
		response['response'] = "error"
		response['result'] = str(ex)
	
	return response

# HMAC construction and Coinbase check
def blockchain_checker(appliance=None):
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
		result = json.loads(opener.open(Request(url), timeout=5).read())
		return True
	except:
		return False


