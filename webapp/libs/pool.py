import json

from urllib2 import urlopen, Request
from urllib2 import HTTPError

from webapp import app
from webapp.libs.utils import row2dict

def loader():
	pass

# remote connection to pool operator's POST methods for instances
def pool_api_instances(instance=None, apitoken=None):

	url = "%s/api/v1/instances/%s?ver=%s&apitoken=%s" % (
		app.config['POOL_APPSPOT_WEBSITE'],
		instance.name,
		app.config['VERSION'],
		apitoken
	)

	# patch up instance for consumption by server
	pool_instance = row2dict(instance)
	pool_instance['flavor'] = instance.flavor.name
	pool_instance['ask'] = instance.flavor.ask
	pool_instance['image'] = instance.image.name
	pool_instance['address'] = instance.address.address

	response = {"response": "success", "result": ""}

	try:
		request = Request(url)
		request.add_header('Content-Type', 'application/json')
		response = json.loads(urlopen(request, json.dumps(pool_instance), timeout=10).read())
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

# remote connection to pool operator's simple GET methods: flavor, image, auth
def pool_api_connect(method="authorization", apitoken="unauthorized"):
	url = "%s/api/v1/%s?ver=%s&apitoken=%s" % (
		app.config['POOL_APPSPOT_WEBSITE'],
		method,
		app.config['VERSION'],
		apitoken
	)

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
