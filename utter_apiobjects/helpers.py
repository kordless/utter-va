import types
from python_jsonschema_objects.classbuilder import ProtocolBase

class ApiSchemaHelper(object):

	@staticmethod
	def fill_object_from_schema(schema, dst):
		for (k, v) in schema.__class__.__dict__['__propinfo__'].iteritems():
			if getattr(schema, k) != None:
				attr = getattr(schema, k)
				if type(attr) == types.ListType:
					setattr(dst, k, attr)
				else:
					setattr(dst, k, attr.as_dict())

	@classmethod
	def fill_schema_from_object(cls, schema, src):
		schema.update(cls.iterate_properties(src, schema.__class__.__dict__['__propinfo__']))

	# iterate over properties of schema and copy properties from src object into schema
	@classmethod
	def iterate_properties(cls, src, properties):
		data = {}
		for (k, v) in properties.iteritems():
			if type(v['type']) == types.StringType:
				if hasattr(src, k) and getattr(src, k) != None:
					data[k] = getattr(src, k)
			elif issubclass(v['type'], ProtocolBase):
				if getattr(src, k) != None:
					data[k] = cls.iterate_properties(getattr(src, k), v['properties'])
		return data
