import json

from urllib2 import urlopen, Request
from urllib2 import HTTPError

from webapp import app
from webapp.libs.utils import row2dict

# remote connection to pool operator's API method for a single instance
def pool_instance(instance=None, appliance=None):

	url = "%s/api/v1/instances/%s/" % (
		app.config['POOL_APPSPOT_WEBSITE'],
		instance.name
	)

	# build the instance packet
	packet = { 
		"appliance": {
			"apitoken": appliance.apitoken,
			"version": app.config['VERSION'],
			"dynamicimages": appliance.dynamicimages,
			"location": {
				"latitude": appliance.latitude,
				"longitude": appliance.longitude
			}
		},
		"instance": {
			"name": instance.name,
			"flavor": instance.flavor.name,
			"ask": instance.flavor.ask,
			"image": instance.image.name,
			"state": instance.state,
			"expires": instance.expires,
			"address": instance.address.address
		}
	}

	# response if things go wrong
	response = {"response": "success", "result": {"message": ""}}

	try:
		request = Request(url)
		request.add_header('Content-Type', 'application/json')
		data = urlopen(request, json.dumps(packet), timeout=10).read()
		response = json.loads(data)
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

# we're a salesman (provider) talking to the broker (pool) to hopefully sell stuff
def pool_salesman(instances=None, appliance=None):

	# form the URL to advertise instance for sale
	url = "%s/api/v1/instances/broker/" % (
		app.config['POOL_APPSPOT_WEBSITE']
	)

	# build the sales packet
	packet = { 
		"appliance": {
			"apitoken": appliance.apitoken, 
			"dynamicimages": appliance.dynamicimages,
			"location": {
				"latitude": appliance.latitude,
				"longitude": appliance.longitude
			}
		},
		"instances": []
	}

	# loop through advertised instances
	for instance in instances:
		# convert to a dict
		pool_instance = row2dict(instance)
		
		# patch in flavor, ask, default image, address
		pool_instance['flavor'] = instance.flavor.name
		pool_instance['ask'] = instance.flavor.ask
		pool_instance['state'] = instance.state
		pool_instance['image'] = instance.image.name
		pool_instance['address'] = instance.address.address

		# add instances to the data packet
		packet['instances'].append(pool_instance)

	# response if things go wrong
	response = {"response": "success", "result": {"message": ""}}

	try:
		request = Request(url)
		request.add_header('Content-Type', 'application/json')
		response = json.loads(urlopen(request, json.dumps(packet), timeout=10).read())
	except HTTPError as ex:
		response['response'] = "fail"
		response['result'] = "Error code %s returned from server." % ex.code
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
def pool_connect(method="authorization", appliance=None):
	url = "%s/api/v1/%s/" % (
		app.config['POOL_APPSPOT_WEBSITE'],
		method
	)

	# build the packet
	packet = { 
		"appliance": {
			"apitoken": appliance.apitoken, 
			"dynamicimages": appliance.dynamicimages,
			"location": {
				"latitude": appliance.latitude,
				"longitude": appliance.longitude
			}
		}
	}

	# response if things go wrong
	response = {"response": "success", "result": {"message": ""}}

	try:
		request = Request(url)
		request.add_header('Content-Type', 'application/json')
		response = json.loads(urlopen(request, json.dumps(packet), timeout=10).read())
	except HTTPError, e:
		response['response'] = "fail"
		response['result'] = "Error code %s returned from server: %s" % (str(e.code), type(e).__name__)
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
