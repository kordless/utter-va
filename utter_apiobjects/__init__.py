import abc
import types

import python_jsonschema_objects as pjs
from python_jsonschema_objects.classbuilder import ProtocolBase

from instance import instance_schema
from instance import appliance_schema


schemes = {
	'InstanceSchema': (instance_schema, 'Instance'),
	'ApplianceSchema': (appliance_schema, 'Appliance'),
}

# template with functions that should be associated to the api schemas
class SchemaTemplate(object):

	def fill_object_from_schema(self, dst):
		for (k, v) in self.__class__.__dict__['__propinfo__'].iteritems():
			if getattr(self, k) != None:
				attr = getattr(self, k)
				if type(attr) == types.ListType:
					setattr(dst, k, attr)
				else:
					setattr(dst, k, attr.as_dict())

	def fill_schema_from_object(self, src):
		self.update(self.iterate_properties(src, self.__class__.__dict__['__propinfo__']))

	# iterate over properties of schema and copy properties from src object into schema
	def iterate_properties(self, src, properties):
		data = {}
		for (k, v) in properties.iteritems():
			if type(v['type']) == types.StringType:
				if getattr(src, k) != None:
					data[k] = getattr(src, k)
			elif issubclass(v['type'], ProtocolBase):
				if getattr(src, k) != None:
					data[k] = self.iterate_properties(getattr(src, k), v['properties'])
		return data

# iterate over schemas to add some functions to them
for (k, v) in schemes.iteritems():
	schemes[k] = getattr(pjs.ObjectBuilder(v[0]).build_classes(), v[1])
	for method in ['fill_schema_from_object',
								'fill_object_from_schema',
								'iterate_properties']:
		setattr(schemes[k], method, SchemaTemplate.__dict__[method])
