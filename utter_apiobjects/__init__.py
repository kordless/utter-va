import python_jsonschema_objects as pjs

from instance import instance_schema
from appliance import appliance_schema
from flavor import flavor_schema
from flavor import flavor_list_schema


schemes = {
	'InstanceSchema': (instance_schema, 'Instance'),
	'ApplianceSchema': (appliance_schema, 'Appliance'),
	'FlavorSchema': (flavor_schema, 'Flavor'),
	'FlavorListSchema': (flavor_list_schema, 'Flavorlist'),
}

# iterate over schemas to add some functions to them
for (k, v) in schemes.iteritems():
	schemes[k] = getattr(pjs.ObjectBuilder(v[0]).build_classes(), v[1])
