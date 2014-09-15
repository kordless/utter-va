import python_jsonschema_objects as pjs

appliance_schema = {
	'type': 'object',
	'title': 'Appliance',
	'properties': {
		'version': {'type': 'string'},
		'dynamicimages': {'type': 'number'},
		'ask': {'type': 'number'},
		'location': {
			'type': 'object',
			'properties': {
				'latitude': {'type': 'string'},
				'longitude': {'type': 'string'},
			},
			'required': ['latitude', 'longitude'],
		},
	},
	'required': ['version', 'dynamicimages', 'location', ],
}

flavor_schema = {
	'type': 'object',
	'title': 'Flavor',
	'properties': {
		'ask': {'type': 'number'},
		'network_up': {'type': 'number'},
		'network_down': {'type': 'number'},
		'disk': {'type': 'number'},
		'vpus': {'type': 'number'},
		'memory': {'type': 'number'},
	},
	'required': ['ask', 'network_up', 'network_down', 'disk', 'vpus', 'memory', ],
}

ip_address_schema = {
	'type': 'object',
	'title': 'IPAddress',
	'properties': {
		'version': {'type': 'number'},
		'scope': { 'enum': [ 'public', 'private', ], },
		'address': {'type': 'string'},
	},
	'required': ['version', 'scope', 'address', ],
}

instance_schema = {
	"$schema": "http://json-schema.org/draft-04/schema#",
	"type": "object",
	'title': 'Instance',
	'properties': {
		'name': {'type': 'string'},
		'image': {'type': 'string'},
		'state': {'type': 'number'},
		'address': {'type': 'string'},
		'console_output': {
			'type': 'array',
			'items': {'type': 'string'},
		},
		'expires': {'type': 'number'},
		'ip_addresses': {
			'type': 'array',
			'items': ip_address_schema,
		},
		'flavor': flavor_schema,
		'appliance': appliance_schema,
	},
	'required': [
		'name', 'image', 'state', 'address',
		'expires', 'flavor', 'appliance',
	],
}

Instance = pjs.ObjectBuilder(instance_schema).build_classes().Instance
