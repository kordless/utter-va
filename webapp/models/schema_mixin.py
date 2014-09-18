import abc

class ModelSchemaMixin(object):

	@abc.abstractproperty
	def schema():
		pass

	# create api schema and fill it with data from self
	def as_dict(self):
		schema = self.schema()
		schema.fill_schema_from_object(self)
		return schema.as_dict()
