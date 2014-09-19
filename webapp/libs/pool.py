import json
import types

import abc
from cgi import escape

from urllib2 import urlopen, Request
from urllib2 import HTTPError

from webapp import app
from webapp.libs.utils import row2dict

from utter_apiobjects import schemes

# provides callback initiation for an instance to the pool operator/callback handler
# calls InstancesHandler() in utter-pool's apihandlers.py 
def pool_instance(url=None, instance=None, next_state=None, appliance=None):

	# response template for if things go wrong
	response = {"response": "success", "result": {"message": ""}}

	try:
		pool_api = PoolApiInstancesUpdate()
		if url:
			pool_api.use_custom_url(url)
		else:
			pool_api.use_custom_url(
				"%s/api/v1/instances/%s/" % (
				app.config['POOL_APPSPOT_WEBSITE'],
				instance.name
			))

		# send instance data to the pool and keep response
		response['result']['instance'] = json.loads(
			instance_json = pool_api.request(json.dumps({
				'appliance': appliance.as_schema().as_dict(),
				'instance': instance.as_schema().as_dict(),
			})))

	except PoolApiException as e:
		response['response'] = "error"
		response['result']['message'] = str(e)
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

	def __init__(self, message, url, data):
		Exception.__init__(self, message)
		self.url = url
		self.data = data
		self.msg = message

	def __str__(self):
		return u'got "{msg}" when calling "{url}"'.format(
			msg=self.msg, url=self.url)


class PoolApiBase(object):
	_uri_base = u'api'
	_api_version = u'v1'
	_content_type = u'application/json'
	_timeout = 10
	_custom_url = None

	# which object on the api should be selected
	@abc.abstractproperty
	def _api_object():
		pass

	# which action should be executed on the object
	@abc.abstractproperty
	def _action():
		pass

	# build the url to the api endpoint
	def _api_url(self):
		if self._custom_url:
			return self._custom_url
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

	# use given url instead of the default one
	def use_custom_url(self, url):
		self._custom_url = url

	# main entry, do the request
	def request(self, data=None):
		try:
			# submit request to the api
			response = urlopen(
					self._build_request(
						self._api_url()), data, self._timeout)

			# if reply code was 2xx
			if str(response.getcode())[:1] == '2':
				return response.read()

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


# interact with instance objects on pool api
class PoolApiInstancesBase(PoolApiBase):
	_api_object = 'instances'


# update instance objects on pool
class PoolApiInstancesUpdate(PoolApiInstancesBase):
	_action = "update"


# interact with flavor objects on pool api
class PoolApiFlavorsBase(PoolApiBase):
	_api_object = 'flavors'


# list flavor flavor objects on pool
class PoolApiFlavorsList(PoolApiFlavorsBase):
	_action = "list"
