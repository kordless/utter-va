import json

from ast import literal_eval
from urllib2 import urlopen, HTTPError
from OpenSSL import SSL

from webapp.libs.exceptions import InvalidAddress, InvalidCallbackURL

# validate a payment address
def blockchain_validate(paymentaddress):
	url = "https://blockchain.info/q/addressbalance/%s" % paymentaddress
	try:
		result = urlopen(url, timeout=10).read()
		response = {"response": "success", "result": result}
	except HTTPError:
		response = {"response": "fail", "result": HTTPError}
	except:
		response = {"response": "fail", "result": "Somthing went wrong with validating address."}
	
	return response

# get an input address
def blockchain_address(paymentaddress, callback_url):
	try:
		url = "https://blockchain.info/api/receive?method=create&address=%s&callback=%s" % (paymentaddress, callback_url)
		result = literal_eval(urlopen(url, timeout=10).read()) # suppose to be safe, but someone should check
		
		# cleanup the returned URL
		result['callback_url'] = json.loads('"%s"' % result['callback_url'])

		# test we're getting good data back
		if result['destination'] != paymentaddress:
			raise InvalidAddress(result['destination'])
		if result['callback_url'] != callback_url:
			raise InvalidCallbackURL(result['callback_url'])

		response = {"response": "success", "result": result}
	
	except HTTPError:
		response = {"response": "fail", "result": HTTPError}
	except InvalidAddress as badaddress:
		response = {"response": "fail", "result": "The %s payment address doesn't match any known instance." % badaddress}
	except InvalidCallbackURL as badurl:
		response = {"response": "fail", "result": "The %s callback URL doesn't match any known instance." % badurl}
	except Exception as ex:
		response = {"response": "fail", "result": "Somthing went wrong with creating address: %s" % ex}

	return response