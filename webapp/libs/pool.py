import json

from cgi import escape

from urllib2 import urlopen, Request
from urllib2 import HTTPError

from webapp import app
from webapp.libs.utils import row2dict

# provides callback initiation for an instance to the pool operator/callback handler
# calls InstancesHandler() in utter-pool's apihandlers.py 
def pool_instance(url=None, instance=None, next_state=None, appliance=None):

	# no custom callback uses pool's default URL
	if not url:
		url = "%s/api/v1/instances/%s/" % (
			app.config['POOL_APPSPOT_WEBSITE'],
			instance.name
		)
		apitoken = appliance.apitoken
	else:
		# mask our apitoken on subsequent redirects
		apitoken = None

	# response template for if things go wrong
	response = {"response": "success", "result": {"message": ""}}
	
	try:
		# getting lazy load errors every once in a while on flavors.  suggested fix here:
		# http://stackoverflow.com/questions/4253176/issue-with-sqlalchemy-parent-instance-someclass-is-not-bound-to-a-session
		# open ticket on this issue is here: https://github.com/StackMonkey/utter-va/issues/57
		flavor = instance.flavor.get()
	except:
		app.logger.error("Lazy load error encountered on getting flavor for instance=(%s)." % instance.name)
		response['response'] = "error"
		response['result'] = "Lazy load error encountered."
		return response

	if instance.image:
		image_name = instance.image.name
	else:
		image_name = "dynamic_image"

	# build the outbound instance packet (to pool or callback service)
	packet = { 
		"appliance": {
			"version": app.config['VERSION'],
			"dynamicimages": appliance.dynamicimages,
			"location": {
				"latitude": appliance.latitude,
				"longitude": appliance.longitude
			}
		},
		"instance": {
			"name": instance.name,
			"flavor": flavor.name,
			"image": image_name,
			"ask": flavor.ask,
			"address": instance.address.address,
			"console_output": [],
			"state": instance.state if next_state == None else next_state,
			"expires": instance.expires,
			"ipv4_address": instance.publicipv4 if instance.publicipv4 else "",
			"ipv6_address": instance.publicipv6 if instance.publicipv6 else "",
			"ipv4_private_address": instance.privateipv4 if instance.privateipv4 else ""
		}
	}

	# append the apitoken for the pool controller for pool auth
	if apitoken:
		packet['appliance']['apitoken'] = apitoken

	# hack up the console object, if there is one
	if instance.console:
		for line in iter(instance.console.splitlines()):
			packet['instance']['console_output'].append(escape(line))
	try:
		# contact the pool and post instance info
		request = Request(url)
		request.add_header('Content-Type', 'application/json')
		data = urlopen(request, json.dumps(packet), timeout=10).read()
		pool_response = json.loads(data)

		# massage the reply a bit for simple callback servers
		if 'response' not in pool_response:
			# no response key, so check if we have an instance key
			if 'instance' in pool_response:
				# overload that into the response object
				response['result']['message'] = "Loaded instance object into response."
				response['result']['instance'] = pool_response['instance']
			else:
				# we don't have a response or an instance
				app.logger.error("Didn't find an instance key in the response from the server.")
				raise ValueError
		else:
			response = pool_response
				
	except HTTPError, e:
		response['response'] = "error"
		response['result']['message'] = "Error code %s returned from server." % str(e.code)
	except IOError as ex:
		response['response'] = "error"
		response['result']['message'] = "Can't contact callback server.  Try again later."
	except ValueError as ex:
		response['response'] = "error"
		response['result']['message'] = "Having issues parsing JSON from the site: %s.  Open a ticket." % type(ex).__name__
	except Exception as ex:
		response['response'] = "error"
		response['result']['message'] = "An error of type %s has occured.  Open a ticket." % type(ex).__name__

	return response

# put instances up for sale
# we're a salesman (provider) talking to the broker (pool) to sell instances
def pool_salesman(instances=None, appliance=None):
	from webapp.libs.openstack import get_stats

	# form the URL to advertise instance for sale
	url = "%s/api/v1/broker/" % (
		app.config['POOL_APPSPOT_WEBSITE']
	)

	# grab the cluster's stats
	try:
		response = get_stats()
		stats = response['result']['stats']
	except:
		stats = {}

	# build the sales packet
	packet = { 
		"appliance": {
			"apitoken": appliance.apitoken, 
			"dynamicimages": appliance.dynamicimages,
			"location": {
				"latitude": appliance.latitude,
				"longitude": appliance.longitude
			},
			"stats": stats
		},
		"instances": []
	}

	# response
	response = {"response": "success", "result": {"message": ""}}

	# loop through advertised instances
	for instance in instances:
		try:
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
		
		except:
			# something didn't go right somewhere, so just nail the instance
			app.logger.error("Instance=(%s) integrity error." % instance.name)
			instance.delete(instance)

	try:
		request = Request(url)
		request.add_header('Content-Type', 'application/json')
		response = json.loads(urlopen(request, json.dumps(packet), timeout=10).read())
		app.logger.info("Appliance has placed quantity=(%s) instances up for sale." % len(instances))

	except HTTPError as ex:
		response['response'] = "error"
		response['result']['message'] = "Error code %s returned from server." % ex.code
	except IOError as ex:
		response['response'] = "error"
		response['result']['message'] = "Can't contact callback server.  Try again later."
	except ValueError as ex:
		response['response'] = "error"
		response['result']['message'] = "Having issues parsing JSON from the site: %s.  Open a ticket." % type(ex).__name__
	except Exception as ex:
		response['response'] = "error"
		response['result']['message'] = "An error of type %s has occured.  Open a ticket." % type(ex).__name__

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
		response['response'] = "error"
		response['result']['message'] = "Error code %s returned from server: %s" % (str(e.code), type(e).__name__)
	except IOError as ex:
		response['response'] = "error"
		response['result']['message'] = "Can't contact callback server.  Try again later."
	except ValueError as ex:
		response['response'] = "error"
		response['result']['message'] = "Having issues parsing JSON from the site: %s.  Open a ticket." % type(ex).__name__
	except Exception as ex:
		response['response'] = "error"
		response['result']['message'] = "An error of type %s has occured.  Open a ticket." % type(ex).__name__

	return response
