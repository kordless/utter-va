import json

import abc
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


class PoolApiException(Exception):
	url = ""
	data = ""

	def __init__(self, message, url, data):
		Exception.__init__(self, message)
		app.logger.error(message)
		self.url = url
		self.data = data


class PoolApiBase(object):
	uri_base = u'api'
	api_version = u'v1'
	content_type = u'application/json'
	timeout = 10
	stringify = {'dump': json.dumps, 'load': json.loads}

	# dict of action keys with data preparation functions as value
	data_preparation_methods = {}

	# which object on the api should be selected
	@abc.abstractproperty
	def api_object():
		pass

	# register the methods to prepare data for sending, keyed by action
	def add_data_preparation_method(self, action, method):
		self.data_preparation_methods[action] = method

	# build the url to the api endpoint
	def api_url(self, action):
		return u'{host}/{base}/{ver}/{api_object}/{action}'.format(
			host=app.config['POOL_APPSPOT_WEBSITE'],
			base=self.uri_base,
			ver=self.api_version,
			api_object=self.api_object,
			action=action)

	# get the request object
	def build_request(self, url):
		request = Request(url)
		request.add_header('Content-Type', self.content_type)
		return request

	# main entry, do the request
	def request(self, action=None, data=None):
		try:
			# submit request to the api
			response = urlopen(
					self.build_request(
						self.api_url(action)),
					self.stringify['dump'](
						self.data_preparation_methods[action](data)),
					self.timeout)

			# if reply code was 2xx
			if response.getcode() / 100 == 2:
				return stringify['load'](response.read())

		# starting from here, handle all error conditions
			err_msg = u"Bad return status from API request."
		except HTTPError, e:
			err_msg = u"Error code %s returned from server: %s" % (str(e.code), type(e).__name__)
		except IOError:
			err_msg = u"Can't contact callback server.  Try again later."
		except ValueError as ex:
			err_msg = u"Having issues parsing JSON from the site: %s.  Open a ticket." \
				% type(ex).__name__
		except Exception as ex:
			err_msg = u"An error of type %s has occured.  Open a ticket." % \
				type(ex).__name__
		raise PoolApiException(
			err_msg,
			self.api_url(),
			data)


# class to act on custom flavors on the pool
class PoolApiCustomFlavors(PoolApiBase):
	api_object = 'custom-flavors'

	def __init__(self):
		PoolApiBase.__init__(self)

		# register data preparation methods
		for (k, v) in {'create': self.prepare_create_data,
								 'delete': self.prepare_delete_data}.items():
				self.add_data_preparation_method(k, v)

	# prepare data to create a custom flavor in the pool
	def prepare_create_data(self, data):
		return {
			'osid': data['flavor'].osid,
			'ask': data['flavor'].ask,
			'description': data['flavor'].description,
			'name': data['flavor'].name,
			'vpus': data['flavor'].vpus,
			'memory': data['flavor'].memory,
			'disk': data['flavor'].disk,
			'launches': data['flavor'].launches,
			'active': data['flavor'].active,
			'hot': data['flavor'].hot,
			'rate': data['flavor'].rate,
			'network': data['flavor'].network}

	# prepare the data to delete a custom flavor in the pool
	def prepare_delete_data(self, data):
		return {
			'osid': data['flavor'].osid,
			'name': data['flavor'].name}
