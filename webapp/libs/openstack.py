import os
import shutil
from subprocess import Popen

from novaclient.v1_1 import client as novaclient
from cinderclient import client as cclient
import keystoneclient.v2_0.client as ksclient
import glanceclient

from webapp import app, db
from webapp.models.models import OpenStack
from webapp.libs.exceptions import OpenStackConfiguration

# used by start instance method to install image if we don't have it already
def image_install(image):
	try:
		# get openstack credentials
		openstack = db.session.query(OpenStack).first()

		# try doing an auth
		try:
			openstack.check()
		except:	
			raise OpenStackConfiguration("Check your OpenStack configuration.")

		# proper way of adding glance image via python
		keystone = ksclient.Client(
			auth_url = openstack.authurl, 
			username = openstack.osusername, 
			password = openstack.ospassword, 
			tenant_id = openstack.tenantid
		)

		glance_endpoint = keystone.service_catalog.url_for(service_type='image')
		glance = glanceclient.Client('1', endpoint=glance_endpoint, token=keystone.auth_token)

		gimage = glance.images.create(
			name = image.name, 
			is_public = False, 
			disk_format = image.diskformat, 
			container_format = image.containerformat,
			location = image.url
		)

		image.osid = gimage.id
		image.update(image)
	
		# set the response	
		response = "success"

	except Exception as ex:
		# update our image to not be installed
		image.osid = ""
		image.active = 0
		image.update(image)

		# set the response
		response = "fail on %s" % ex

	return ({"response": response, "image": image})

def image_remove(image):
	try:
		# get the cluster configuration
		openstack = db.session.query(OpenStack).first()
	
		# no configuration present
		if not openstack:
			raise OpenStackConfiguration("OpenStack configuration isn't complete.")
	
		# connect to nova
		nova = novaclient.Client(openstack.osusername, openstack.ospassword, openstack.tenantname, openstack.authurl, service_type="compute")

		# delete the selected image
		nova.images.delete(image.osid)

		# udpate the images db to reflect
		image.osid = ""
		image.active = 0
		image.update(image)
		
		# response
		response = "success"

	except Exception as ex:
		# update our image to not be installed
		image.osid = ""
		image.active = 0
		image.update(image)

		response = "fail on %s" % ex

	return ({"response": response, "image": image})

# used by instance start method to install a flavor if we don't have it 
def flavor_install(flavor):
	try:
		# get the cluster configuration
		openstack = db.session.query(OpenStack).first()
		
		# what happens if they haven't configured it already?
		if not openstack:
			raise OpenStackConfiguration("OpenStack configuration isn't complete.")

		# establish connection to openstack
		nova = novaclient.Client(openstack.osusername, openstack.ospassword, openstack.tenantname, openstack.authurl, service_type="compute")
		
		# create the new flavor
		osflavor = nova.flavors.create(flavor.name, flavor.memory, flavor.vpus, flavor.disk, None, 0, 0, 1.0, True)
		osflavor.set_keys({"provider": app.config["POOL_NAME"]})

		# update the flavor database with id
		flavor.osid = osflavor.id
		flavor.update(flavor)
		response = "success"

	except Exception as ex:
		response = "fail on %s" % ex
		print response
		
	return ({"response": response, "flavor": flavor})

def flavor_remove(flavor):
	try:
		openstack = db.session.query(OpenStack).first()
	
		# what happens if they haven't configured it already?
		if not openstack:
			raise OpenStackConfiguration
	
		# establish connection to openstack and delete flavor
		nova = novaclient.Client(openstack.osusername, openstack.ospassword, openstack.tenantname, openstack.authurl, service_type="compute")
		osflavor = nova.flavors.delete(flavor.osid)

		# update our flavor to not be installed
		flavor.osid = ""
		flavor.active = 0
		flavor.update(flavor)
		
		# success
		response = "success"

	except Exception as ex:
		# update our flavor to not be installed
		flavor.osid = ""
		flavor.active = 0
		flavor.update(flavor)

		response = "fail on %s" % ex
		print response

	return ({"response": response, "flavor": flavor})

def instance_start(instance):
	# get the cluster configuration
	openstack = OpenStack.get()

	# default response
	response = {"response": "success", "result": {}}

	print instance.image.osid, instance.flavor.osid

	# if we can't talk to OpenStack
	if not openstack:
		response['response'] = "fail"
		response['result'] = "OpenStack configuration entry missing."
	elif not openstack.check():
		response['response'] = "fail"
		response['result'] = "Can't communicate with OpenStack cluster."
	else:
		nova = novaclient.Client(openstack.osusername, openstack.ospassword, openstack.tenantname, openstack.authurl, service_type="compute")
		detail = nova.servers.create(name=instance.name, image=instance.image.osid, flavor=instance.flavor.osid, key_name="id-kord")

	return response

def instance_suspend():
	pass

def instance_decomission():
	pass