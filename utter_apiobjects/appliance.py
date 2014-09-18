appliance_schema = {
	'type': 'object',
	'title': 'Appliance',
	'properties': {
		'version': {'type': 'string'},
		'dynamicimages': {'type': 'number'},
		'apitoken': {'type': 'string'},
		'latitude': {'type': 'string'},
		'longitude': {'type': 'string'},
		},
	'required': ['version', 'dynamicimages', 'apitoken', 'longitude', 'latitude'],
}
