#!/usr/bin/python
import sys
import time
import json
import hmac
import hashlib

from urllib2 import urlopen, Request, build_opener, HTTPError
from urllib import quote

# HMAC construction and Coinbase query
def coinbase_send_money(address=None, amount=None, user_fee=None, credentials=None):
	url = "https://coinbase.com/api/v1/transactions/send_money"
	
	# create urlib2 opener and a nonce for the session
	opener = build_opener()
	nonce = int(time.time() * 1e6)

	# massage data to fit coinbase's use of parameterized dicts
	data = {
		"transaction": {
			"to": str(address),
			"amount": str(amount),
			"user_fee": str(user_fee)
		}
	}

	data = "transaction[to]=%s&transaction[amount]=%s" % (address, amount)
	print "submitting with '%s' as data payload.." % data
	# create and sign the message
	message = str(nonce) + url + ('' if data is None else data)
	signature = hmac.new(str(credentials['cbapisecret']), message, hashlib.sha256).hexdigest()

	# pop parameters into the headers
	opener.addheaders = [
		('ACCESS_KEY', credentials['cbapikey']),
		('ACCESS_SIGNATURE', signature),
		('ACCESS_NONCE', nonce),
	]

	# initialize response object
	response = {"response": "success", "result": {}}

	# call coinbase

	result = json.loads(opener.open(Request(url, data), timeout=10).read())
	response['result'] = result
	try:
		pass
	except HTTPError as ex:
		response['response'] = "fail"
		response['result'] = "An error of type %s has occured.  Open a ticket." % type(ex).__name__
	except CoinBaseAddressBuild as ex:
		response['response'] = "fail"
		response['result'] = str(ex)
	
	return response

# check credentials
def coinbase_checker(credentials=None):
	url = "https://coinbase.com/api/v1/authorization"
	
	# create urlib2 opener and a nonce for the session
	opener = build_opener()
	nonce = int(time.time() * 1e6)

	# create and sign the message
	message = str(nonce) + url
	signature = hmac.new(str(credentials['cbapisecret']), message, hashlib.sha256).hexdigest()

	# pop parameters into the headers
	opener.addheaders = [
		('ACCESS_KEY', credentials['cbapikey']),
		('ACCESS_SIGNATURE', signature),
		('ACCESS_NONCE', nonce),
	]

	# call coinbase
	try:
		result = json.loads(opener.open(Request(url), timeout=5).read())
		return True
	except:
		return False

# big important stuff happens here
if __name__ == "__main__":
	
	# test account secret and key for coinbase
	credentials = { 
		"cbapisecret": "",
		"cbapikey": ""
	}

	# if we have good credentials
	if coinbase_checker(credentials):
		print "Credentials seem to be working."

		# test address
		address = "1DY64V5v2fJGPvnbhA9bXAxrmKSTeDNQGJ"
		amount = '0.00004'
		user_fee = '0.00000'

		# do the call
		response = coinbase_send_money(address, amount, user_fee, credentials)

		# print result
		print response