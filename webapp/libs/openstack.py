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
from webapp.libs.exceptions import OpenStackConfiguration, OpenStackError
from webapp.libs.utils import message, row2dict

def nova_connection():
	# openstack connection
	openstack = OpenStack.get()

	# establish connection to openstack
	connection = novaclient.Client(
		openstack.osusername,
		openstack.ospassword,
		openstack.tenantname,
		openstack.authurl,
		service_type="compute"
	)

	return connection

# get stats for appliance cluster
def get_stats():
	# default response
	response = {"response": "success", "result": {"message": ""}}

	# openstack settings
	openstack = OpenStack.get()

	# try establishing nova connection
	try:
		nova = nova_connection()
	except:
		response['response'] = "error"
		response['result'] = "Can't communicate with OpenStack cluster."
		app.logger.error("Can't communicate with OpenStack cluster.")
		return response
	
	try:
		# grab the infos from openstack
		cluster_quota = nova.quotas.get(openstack.tenantid)
		
		# build the stats object
		stats = {
			"quota": {
				"cores": cluster_quota.cores,
				"fixips": cluster_quota.fixed_ips,
				"instances": cluster_quota.instances,
				"ram": cluster_quota.ram
			},
			"hypervisors": []
		}

	except:
		response['response'] = "error"
		response['result']['message'] = "OpenStack quota list unavailable."
		app.logger.error("The OpenStack cluster is refusing to provide quota information.")
		return response

	# try to talk to the hypervisor list function
	try:
		cluster_hypervisors = nova.hypervisors.list()
			
		# loop through hypervisors
		for cluster_hypervisor in cluster_hypervisors:
			hypervisor = {}

			hypervisor['hypervisor_hostname'] = cluster_hypervisor.hypervisor_hostname
			hypervisor['is_loaded'] = cluster_hypervisor.is_loaded()
			hypervisor['current_workload'] = cluster_hypervisor.current_workload
			hypervisor['local_gb'] = cluster_hypervisor.local_gb
			hypervisor['local_gb_used'] = cluster_hypervisor.local_gb_used
			hypervisor['memory_mb'] = cluster_hypervisor.memory_mb
			hypervisor['memory_mb_used'] = cluster_hypervisor.memory_mb_used
			hypervisor['free_disk_gb'] = cluster_hypervisor.free_disk_gb
			hypervisor['free_ram_mb'] = cluster_hypervisor.free_ram_mb
			hypervisor['vcpus'] = cluster_hypervisor.vcpus
			hypervisor['vcpus_used'] = cluster_hypervisor.vcpus_used
			hypervisor['running_vms'] = cluster_hypervisor.running_vms
			hypervisor['disk_available_least'] = cluster_hypervisor.disk_available_least

			stats['hypervisors'].append(hypervisor)

	except:
		# nevermind then
		app.logger.error("The OpenStack cluster is refusing to provide hypervisor information.")
		pass

	# return one or both of quota and hypervisor stats
	response['response'] = "success"
	response['result']['message'] = "OpenStack stats detail."
	response['result']['stats'] = stats
	return response		

# verify image is installed or install image correctly if it's not
def image_verify_install(image):
	# build the response
	response = {"response": "", "result": {"message": "", "image": {}}}

	# get the cluster configuration
	openstack = db.session.query(OpenStack).first()

	try:
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
			app.logger.info("Installing image=(%s) into the OpenStack cluster. %s" % (image.name, ex))
			install_image = True

		if install_image:
			# install remote or local image into openstack
			if image.local_url == "" or image.local_url is None:
				location = image.url
			else:
				location = image.local_url

			osimage = glance.images.create(
				name = image.name, 
				is_public = False, 
				disk_format = image.diskformat, 
				container_format = image.containerformat,
				location = location
			)

			# update updated time for image
			pattern = '%Y-%m-%dT%H:%M:%S'
			image.updated = int(time.mktime(time.strptime(osimage.created_at, pattern)))

			# we *should* have an osimage.id here. If not, we'll bomb 
			# to the exception below and wipe the entry from the appliance.
			image.osid = osimage.id
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
		response['response'] = "error"
		response['result']['image'] = row2dict(image)
		response['result']['message'] = "%s" % ex

		app.logger.error("Failed to install image=(%s) into the OpenStack cluster. %s" % (image.name, ex))

	return response

# delete images
def image_delete(image):
	# build the response
	response = {"response": "", "result": {"message": ""}}

	# get the cluster configuration
	openstack = db.session.query(OpenStack).first()

	try:
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

		# try to delete the sucker
		glance.images.delete(image.osid)

		# response
		response['response'] = "success"
		response['result']['message'] = "Image deleted."

	except Exception as ex:
		# response
		response['response'] = "error"
		response['result']['message'] = "Image delete failed: %s" % ex
		
		app.logger.error("Failed to delete image=(%s) from the OpenStack cluster." % image.name)

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
		nova = nova_connection()

		# handle exception from nova if not found
		try:
			targetflavor = None
			# look up the flavor by name and stop on it
			osflavors = nova.flavors.list()
			for osflavor in osflavors:
				if osflavor.name == flavor.name:
					targetflavor = osflavor
					break
		except:
			# no flavor found
			targetflavor = None

		# check for install needed
		install_flavor = False
		if targetflavor:
			# check flavor specs match
			if targetflavor.vcpus != flavor.vpus: # vpus wrong
				install_flavor = True
			if targetflavor.disk != flavor.disk: # disk size wrong
				install_flavor = True 
			if targetflavor.ram != flavor.memory: # memory wrong
				install_flavor = True

			# check the flavor quota keys match network limit
			osikeys = targetflavor.get_keys()

			if 'quota:inbound_average' in osikeys and 'quota:outbound_average' in osikeys:
				if flavor.network != int(osikeys['quota:inbound_average']):
					install_flavor = True
				if flavor.network != int(osikeys['quota:outbound_average']):
					install_flavor = True
			else:
				install_flavor = True
			
		else:
			# no flavor found
			install_flavor = True

		# install the flavor
		if install_flavor:
			if targetflavor:
				try:
					# remove the old flavor
					nova.flavors.delete(targetflavor.id)
				except:
					app.logger.info("Could not remove the old flavor=(%s) from the OpenStack cluster." % flavor.name)

			# create the new flavor
			targetflavor = nova.flavors.create(
				flavor.name,
				flavor.memory,
				flavor.vpus,
				flavor.disk,
				flavorid='auto',
				ephemeral=0,
				swap=0,
				rxtx_factor=1.0,
				is_public=True
			)

			# set bandwidth
			targetflavor.set_keys({"quota:inbound_average": flavor.network})
			targetflavor.set_keys({"quota:outbound_average": flavor.network})

			app.logger.info("Installed flavor=(%s) into the OpenStack cluster." % flavor.name)

		# update the flavor database with id
		flavor.osid = targetflavor.id
		flavor.update(flavor)

		# response
		response['response'] = "success"
		response['result']['message'] = "Flavor added."
		response['result']['flavor'] = row2dict(flavor)

	except Exception as ex:
		# update our flavor to not be installed
		flavor.osid = ""
		flavor.active = 0
		flavor.update()

		# response
		response['response'] = "error"
		response['result']['flavor'] = row2dict(flavor)
		response['result']['message'] = "%s" % ex
		
		app.logger.error("Failed to install flavor=(%s) into the OpenStack cluster. %s" % (flavor.name, ex))

	return response

def instance_start(instance):
	# default response
	response = {"response": "success", "result": {"message": "", "instance": {}}}

	# try establishing nova connection
	try:
		nova = nova_connection()
	except:
		response['response'] = "error"
		response['result'] = "Can't communicate with OpenStack cluster."
		app.logger.error("Can't communicate with OpenStack cluster.")
		return response

	try:
		# check if we already have a server named this running
		servers = nova.servers.list()
		for server in servers:
			if server.name == instance.name:
				response['response'] = "success"
				response['result']['message'] = "Server is already running."
				response['result']['server'] = server
				return response

		# otherwise, start the server instances
		server = nova.servers.create(
			name=instance.name, 
			image=instance.image.osid,
			flavor=instance.flavor.osid,
			userdata=instance.post_creation
		)

		# response
		response['result']['message'] = "OpenStack instance started."
		response['result']['server'] = server

		app.logger.info("Started instance=(%s)." % instance.name)
	
	except Exception as ex:
		# response
		response['response'] = "error"
		response['result']['message'] = "OpenStack instance start failed."

		app.logger.error("Failed to start instance=(%s)." % instance.name)

	return response


def instance_console(instance):
	# default response
	response = {"response": "success", "result": {"message": "", "server": {}}}

	# try establishing nova connection
	try:
		nova = nova_connection()
	except:
		response['response'] = "error"
		response['result'] = "Can't communicate with OpenStack cluster."
		app.logger.error("Can't communicate with OpenStack cluster.")

		return response

	try:
		# grab the server info from openstack
		console = nova.servers.get_console_output(instance.osid, 40)
	
		response['response'] = "success"
		response['result']['message'] = "OpenStack instance console output."
		response['result']['console'] = console
		
	except:
		response['response'] = ""
		response['result']['message'] = "OpenStack console not found."

	return response

def instance_info(instance):
	# default response
	response = {"response": "success", "result": {"message": "", "server": {}}}

	# try establishing nova connection
	try:
		nova = nova_connection()
	except:
		response['response'] = "error"
		response['result'] = "Can't communicate with OpenStack cluster."
		app.logger.error("Can't communicate with OpenStack cluster.")
		return response

	try:
		# grab the server info from openstack
		server = nova.servers.get(instance.osid)
	
		response['response'] = "success"
		response['result']['message'] = "OpenStack instance detail."
		response['result']['server'] = server

	except:
		response['response'] = "error"
		response['result']['message'] = "OpenStack instance not found."
		app.logger.error("Failed to fetch info for instance=(%s)." % instance.name)	

	return response

def instance_suspend(instance):
	# default response
	response = {"response": "success", "result": {"message": "", "server": {}}}

	# try establishing nova connection
	try:
		nova = nova_connection()
	except:
		response['response'] = "error"
		response['result']['message'] = "Can't communicate with OpenStack cluster."
		app.logger.error("Can't communicate with OpenStack cluster.")
		return response

	# suspend the instance
	server = nova.servers.suspend(instance.osid)

	# response
	response['result']['message'] = "OpenStack instance suspended."
	response['result']['server'] = server
	app.logger.info("OpenStack instance=(%s) suspended." % instance.name)	
	
	return response

def instance_resume(instance):
	# default response
	response = {"response": "success", "result": {"message": "", "server": {}}}

	# try establishing nova connection
	try:
		nova = nova_connection()
		
		# resume the instance
		server = nova.servers.resume(instance.osid)
		app.logger.info("OpenStack instance=(%s) resumed." % instance.name)
	
		# response
		response['result']['message'] = "OpenStack instance resumed."
		response['result']['server'] = server
	
	except:
		response['response'] = "error"
		response['result']['message'] = "Can't communicate with OpenStack cluster."
		app.logger.error("Can't communicate with OpenStack cluster.")

	return response

def instance_decommission(instance):
	# default response
	response = {"response": "success", "result": {"message": "", "server": {}}}

	try:
		# establish a connection to nova
		nova = nova_connection()

		# get the server's info and delete
		server = nova.servers.get(instance.osid)
		server.delete()
		app.logger.info("OpenStack instance=(%s) decomissioned." % instance.name)
		
		# search by name and delete any matches
		# this attempts to address the observed behavior of an extra 
		# copy of the same instance being started by manage.py  
		servers = nova.servers.list()
		for server in servers:
			if server.name == instance.name:
				server.delete()
				app.logger.info("OpenStack instance=(%s) decomissioned by name." % server.name)
		
		# build response
		response['result']['message'] = "Server stopped."
		response['result']['server'] = server

	except:
		# oh noes, something went wrong
		response['response'] = "error"
		response['result']['message'] = "Failed to decomission OpenStack instance."
	
	return response
