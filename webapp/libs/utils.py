import string, random, json
from ast import literal_eval
from urllib2 import urlopen, HTTPError
from OpenSSL import SSL
from webapp import app
from webapp.api.models import Images, Flavors, Instances
from webapp.libs.exceptions import InvalidAddress, InvalidCallbackURL

def generate_token(size=64, caselimit=False):
	if caselimit:
		characters  = string.ascii_lowercase + string.digits
	else:
		characters  = string.ascii_uppercase + string.ascii_lowercase + string.digits
	token = ''.join(random.choice(characters) for x in range(size))
	return token

def server_connect(method, apitoken):
	url = app.config['APP_WEBSITE'] + '/api/%s?ver=%s&apitoken=%s' % (method, app.config['VERSION'], apitoken)
	response = urlopen(url, timeout=10).read()
	return json.loads(response)

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

def sync_remote(apitoken):
	# pulls in remote flavors and images available for use from the pool operator
	# similar functionality is provided by the Appliance object model and config view
	
	# check version of virtual appliance
	version = False

	try:
		version = server_connect("version", apitoken)
	except AttributeError as ex:
		configure_blurb()
	except IOError as ex:
		error = "Can't contact central server.  Try again later."
	except ValueError as ex:
		error = "Having issues parsing JSON from the site: %s.  Open a ticket." % type(ex).__name__
	except Exception as ex:
		error = "An error of type %s has occured.  Open a ticket." % type(ex).__name__
	
	if not version:
		return {"response": "fail on %s" % error}
	
	# update list of current images in db
	remoteimages = False
	try:
		remoteimages = server_connect("images", apitoken)
	except AttributeError as ex:
		configure_blurb()
	except IOError as ex:
		error = "Can't contact central server.  Try again later."
	except ValueError as ex:
		error = "Having issues parsing JSON from the site: %s.  Open a ticket." % type(ex).__name__
	except Exception as ex:
		error = "An error of type %s has occured.  Open a ticket." % type(ex).__name__

	if not remoteimages:
		return {"response": "fail on %s" % error}

	# update images from server
	images = Images()
	images.sync(remoteimages)

	# update list of current flavors in db
	remoteflavors = False
	try:
		remoteflavors = server_connect("flavors", apitoken)
	except AttributeError as ex:
		configure_blurb()
	except IOError as ex:
		error = "Can't contact central server.  Try again later."
	except ValueError as ex:
		error = "Having issues parsing JSON from the site: %s.  Open a ticket." % type(ex).__name__
	except Exception as ex:
		error = "An error of type %s has occured.  Open a ticket." % type(ex).__name__

	if not remoteflavors:
		return {"response": "fail on %s" % error}

	# update flavors from server
	flavors = Flavors()
	flavors.sync(remoteflavors)

	return {"response": "success"}