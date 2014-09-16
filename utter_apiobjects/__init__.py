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

class SchemaTemplate(object):

	def fill_from_object(self, src):
		self.update(self.iterate_properties(src, self.__class__.__dict__['__propinfo__']))

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

for (k, v) in schemes.iteritems():
	schemes[k] = getattr(pjs.ObjectBuilder(v[0]).build_classes(), v[1])
	for method in ['fill_from_object', 'iterate_properties']:
		setattr(schemes[k], method, SchemaTemplate.__dict__[method])

