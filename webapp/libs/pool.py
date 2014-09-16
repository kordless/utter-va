import json
import types

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

	# response template for if things go wrong
	response = {"response": "success", "result": {"message": ""}}

	# hack up the console object, if there is one
	if instance.console:
		for line in iter(instance.console.splitlines()):
			packet['instance']['console_output'].append(escape(line))
	try:
		# contact the pool and post instance info
		request = Request(url)
		request.add_header('Content-Type', 'application/json')
		data = urlopen(request, instance.serialize(), timeout=10).read()
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
	_uri_base = u'api'
	_api_version = u'v1'
	_content_type = u'application/json'
	_timeout = 10
	_stringify = {'dump': json.dumps, 'load': json.loads}

	# keys/properties that should be taken from data to be passed to api
	# format specification:
	#   first letter of dict key must be 'k' for 'key' or 'p' for 'property'
	#   second letter must be ':'
	#   starting from third letter on comes the value
	#   values of final leaf nodes are names to be used in data passed to pool
	_data_keys = {}

	# which object on the api should be selected
	@abc.abstractproperty
	def _api_object():
		pass

	# which action should be executed on the object
	@abc.abstractproperty
	def _action():
		pass

	def __init__(self, appliance):
		self._appliance = appliance

	# take an already existing dict of data and add the authentication data
	def _add_authentication_data(self, data):
		data['appliance'] = {
			"apitoken": self._appliance.apitoken,
			"dynamicimages": self._appliance.dynamicimages,
			"location": {
				"latitude": self._appliance.latitude,
				"longitude": self._appliance.longitude
			}}
		return data

	# build the url to the api endpoint
	def _api_url(self):
		return u'{host}/{base}/{ver}/{api_object}/{action}'.format(
			host=app.config['POOL_APPSPOT_WEBSITE'],
			base=self._uri_base,
			ver=self._api_version,
			api_object=self._api_object,
			action=self._action)

	# get the request object
	def _build_request(self, url):
		request = Request(url)
		request.add_header('Content-Type', self._content_type)
		return request

	# extract the required data from the passed object
	def _extract_data(self, data):
		extracted_data = {}
		self._extract_data_from_node(data, self._data_keys, extracted_data)
		return extracted_data

	# iterate over nodes of tree
	def _extract_data_from_node(self, node, keys, extracted_data):

		# loop over the given keys
		for node_key in keys.keys():

			# get named property
			if node_key[:1] == "p":
				sub_node = getattr(node, node_key[2:])

			# get named key
			if node_key[:1] == "k":
				sub_node = node[node_key[2:]]

			# if string we must have reached a leaf
			if type(sub_node) in types.StringTypes or \
					type(sub_node) == types.IntType or \
					type(sub_node) == types.BooleanType:
				extracted_data[keys[node_key]] = sub_node
				continue

			# if none we must have reached a leaf
			if type(sub_node) is types.NoneType:
				extracted_data[keys[node_key]] = ""
				continue

			# otherwise keep looping down into the rabbit hole
			self._extract_data_from_node(sub_node, keys[node_key], extracted_data)

	# main entry, do the request
	def request(self, data=None):
		try:
			# submit request to the api
			response = urlopen(
					self._build_request(
						self._api_url()),
					self._stringify['dump'](
						self._add_authentication_data(
							self._extract_data(data))),
					self._timeout)

			# if reply code was 2xx
			if response.getcode() / 100 == 2:
				return self._stringify['load'](response.read())

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
			self._api_url(),
			data)


# class to act on custom flavors on the pool
class CustomFlavorsPoolApiBase(PoolApiBase):
	_api_object = 'flavors'


# class to create new flavors on pool
class CustomFlavorsPoolApiCreate(CustomFlavorsPoolApiBase):
	_action = "create"
	_data_keys = {
		'k:flavor': {
			'p:ask': 'ask',
			'p:description': 'description',
			'p:name': 'name',
			'p:vpus': 'vpus',
			'p:memory': 'memory',
			'p:disk': 'disk',
			'p:launches': 'launches',
			'p:active': 'active',
			'p:hot': 'hot',
			'p:rate': 'rate',
			'p:network_down': 'network_down',
			'p:network_up': 'network_up'}}


# class to create new flavors on pool
class CustomFlavorsPoolApiUpdate(CustomFlavorsPoolApiCreate):
	_action = "update"


# class to delete flavors on pool
class CustomFlavorsPoolApiDelete(CustomFlavorsPoolApiBase):
	_action = "delete"
	_data_keys = {
		'k:flavor': {
			'p:osid': 'osid',
			'p:name': 'name'}}
