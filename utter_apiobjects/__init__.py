import python_jsonschema_objects as pjs

from instance import instance_schema

InstanceSchema = pjs.ObjectBuilder(instance_schema).build_classes().Instance
