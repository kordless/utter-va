from utter_apiobjects.flavor import flavor_schema

image_schema = {
	'type': 'object',
	'title': 'Image',
	'properties': {
		'name': {'type': 'string'}
	},
	'required': ['name'],
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
		'image': image_schema,
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
	},
	'required': [
		'name', 'image', 'state', 'address',
		'expires', 'flavor',
	],
}
