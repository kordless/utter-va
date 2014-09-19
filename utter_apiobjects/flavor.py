
flavor_schema = {
	'type': 'object',
	'title': 'Flavor',
	'properties': {
		'osid': {'type': 'string'},
		'name': {'type': 'string'},
		'description': {'type': 'string'},
		'rate': {'type': 'number'},
		'hot': {'type': 'number'},
		'launches': {'type': 'number'},
		'flags': {'type': 'number'},
		'active': {'type': 'boolean'},
		'source': {'type': 'number'},
		'ask': {'type': 'number'},
		'network_up': {'type': 'number'},
		'network_down': {'type': 'number'},
		'disk': {'type': 'number'},
		'vpus': {'type': 'number'},
		'memory': {'type': 'number'},
	},
	'required': [
		'name', 'hot', 'launches', 'flags', 'source', 'network_up', 'network_down',
		'disk', 'vpus', 'memory', ],
}

flavor_list_schema = {
	'type': 'object',
	'title': 'FlavorList',
	'properties': {
		'items': {
			'type': 'array',
			'items': flavor_schema,
		},
	},
}
