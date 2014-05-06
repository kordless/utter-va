import os
import shutil
import time

from subprocess import Popen

from flask import jsonify

from novaclient.v1_1 import client as novaclient
from cinderclient import client as cclient
import keystoneclient.v2_0.client as ksclient
import glanceclient

from webapp import app, db
from webapp.models.models import OpenStack
from webapp.libs.exceptions import OpenStackConfiguration
from webapp.libs.utils import message, row2dict

# verify image is installed or install image correctly if it's not
def image_verify_install(image):
	# build the response
	response = {"response": "", "result": {"message": "", "image": {}}}

	openstack = db.session.query(OpenStack).first()

	try:
		# get the cluster configuration
		openstack = db.session.query(OpenStack).first()
	
		# no configuration present
		if not openstack:
			raise OpenStackConfiguration("OpenStack configuration isn't complete.")
	
		# proper way of getting glance image via python
		keystone = ksclient.Client(
			auth_url = openstack.authurl, 
			username = openstack.osusername, 
			password = openstack.ospassword, 
			tenant_id = openstack.tenantid
		)

		glance_endpoint = keystone.service_catalog.url_for(service_type='image')
		glance = glanceclient.Client('1', endpoint=glance_endpoint, token=keystone.auth_token)

		# if image doesn't exist, or exists and is marked deleted, 
		# install a new image
		install_image = False
		try:
			osimage = glance.images.get(image.osid)
			# os image was deleted somehow
			if osimage.deleted == True:
				install_image = True
			
			# check update times
			pattern = '%Y-%m-%dT%H:%M:%S'
			image_epoch = int(time.mktime(time.strptime(osimage.created_at, pattern)))
			
			# if we have an old copy in openstack, we delete it and install new
			if image_epoch < image.updated:
				install_image = True
				glance.images.delete(image.osid)
		
		except Exception as ex:
			osimage = None # we're here because osimage was None
			install_image = True

		if install_image:
			# install remote or local image into openstack
			if image.local_url != "":
				location = image.local_url
			else:
				location = image.url

			osimage = glance.images.create(
				name = image.name, 
				is_public = False, 
				disk_format = image.diskformat, 
				container_format = image.containerformat,
				location = location
			)

		# we *should* have an osimage.id here. If not, we'll bomb 
		# to the exception below and wipe the entry from the appliance.
		image.osid = osimage.id

		# update updated time for image
		pattern = '%Y-%m-%dT%H:%M:%S'
		image.updated = int(time.mktime(time.strptime(osimage.created_at, pattern)))
		image.update()

		# response
		response['response'] = "success"
		response['result']['image'] = row2dict(image)
		response['result']['message'] = "Image installed."

	except Exception as ex:
		# update our image to not be installed
		try:
			glance.images.delete(image.osid)
		except:
			# image.osid didn't exist, or image wasn't installed
			pass

		# zero this image on the appliance
		image.osid = ""
		image.active = 0
		image.update()

		# response
		response['response'] = "fail"
		response['result']['image'] = row2dict(image)
		response['result']['message'] = "%s" % ex

	return response

# used by instance start method to install a flavor if we don't have it
# or re-install a flavor if the flavor doesn't match appliance specs
def flavor_verify_install(flavor):
	# build the response
	response = {"response": "", "result": {"message": "", "flavor": {}}}
	
	try:
		# get the cluster configuration
		openstack = db.session.query(OpenStack).first()
		
		# what happens if they haven't configured it already?
		if not openstack:
			raise OpenStackConfiguration("OpenStack configuration isn't complete.")

		# establish connection to openstack
		nova = novaclient.Client(
			openstack.osusername,
			openstack.ospassword,
			openstack.tenantname,
			openstack.authurl,
			service_type="compute"
		)

		# handle exception from nova if not found
		try:
			# look up the flavor by name and stop on it
			osflavors = nova.flavors.list()
			for osflavor in osflavors:
				if osflavor.name == flavor.name:
					break
		except:
			# no flavor found
			osflavor = None

		# check for install needed
		install_flavor = False
		if osflavor:
			# check flavor specs match
			if osflavor.vcpus != flavor.vpus: # vpus wrong
				install_flavor = True
			if osflavor.disk != flavor.disk: # disk size wrong
				install_flavor = True 
			if osflavor.ram != flavor.memory: # memory wrong
				install_flavor = True

			# check the flavor quota keys match network limit
			osikeys = osflavor.get_keys()
			if flavor.network != int(osikeys['quota:inbound_average']):
				install_flavor = True
			if flavor.network != int(osikeys['quota:outbound_average']):
				install_flavor = True
		else:
			# no flavor found
			install_flavor = True

		# install the flavor
		if install_flavor:
			if osflavor:
				try:
					# remove the old flavor
					nova.flavors.delete(osflavor.id)
				except:
					pass

			# create the new flavor
			osflavor = nova.flavors.create(
				flavor.name,
				flavor.memory,
				flavor.vpus,
				flavor.disk,
				None,
				0,
				0,
				1.0,
				True
			)

			# set provider info
			osflavor.set_keys({"provider": app.config["POOL_NAME"]})

			# set bandwidth
			osflavor.set_keys({"quota:inbound_average": flavor.network})
			osflavor.set_keys({"quota:outbound_average": flavor.network})

		# update the flavor database with id
		flavor.osid = osflavor.id
		flavor.update(flavor)

		# response
		response['response'] = "success"
		response['result']['message'] = "Flavor added."
		response['result']['flavor'] = row2dict(flavor)

	except Exception as ex:
		# update our image to not be installed
		flavor.osid = ""
		flavor.active = 0
		flavor.update()

		# response
		response['response'] = "fail"
		response['result']['flavor'] = row2dict(flavor)
		response['result']['message'] = "%s" % ex
		
	return response

def instance_start(instance):
	# get the cluster configuration
	openstack = OpenStack.get()

	# default response
	response = {"response": "success", "result": {}}

	# if we can't talk to OpenStack
	if not openstack:
		response['response'] = "fail"
		response['result'] = "OpenStack configuration entry missing."
	elif not openstack.check():
		response['response'] = "fail"
		response['result'] = "Can't communicate with OpenStack cluster."
	else:

		# establish connection to openstack
		nova = novaclient.Client(
			openstack.osusername,
			openstack.ospassword,
			openstack.tenantname,
			openstack.authurl,
			service_type="compute"
		)

		# check if we already have a server named this running

		# start the server
		server = nova.servers.create(
			name=instance.name, 
			image=instance.image.osid,
			flavor=instance.flavor.osid, 
			key_name="id-kord"
		)

	print server

	return response

def instance_suspend():
	pass

def instance_decomission():
	pass