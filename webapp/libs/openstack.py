import os
import shutil
import time

from subprocess import Popen

from flask import jsonify

from novaclient.v1_1 import client as novaclient
from novaclient import exceptions as nova_exceptions
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

def keystone_client():
	openstack = OpenStack.get()
	# authenticate with keystone
	return ksclient.Client(
		auth_url = openstack.authurl, 
		username = openstack.osusername, 
		password = openstack.ospassword, 
		tenant_id = openstack.tenantid
	)

def glance_client():
	keystone = keystone_client()
	glance_endpoint = keystone.service_catalog.url_for(service_type='image')
	# establish connection to glance
	return glanceclient.Client('1', endpoint=glance_endpoint, token=keystone.auth_token, timeout=10)

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

def create_os_image(**kwargs):
	return glance_client().images.create(
		name = kwargs['name'],
		is_public = False,
		disk_format = 'qcow2',
		container_format = 'bare',
		location = kwargs['url']
	)

def ensure_image_is_deleted(image_id):
	glance = glance_client()
	image = glance.images.get(image_id)
	if image:
		image.delete()

def list_flavors(filter_by=None):
	response = {"response": "success", "result": {"message": ""}}
	try:
		# get flavors from openstack cluster and filter them to only include ones
		# that have a key matching the filter critera, or if filter_by is None just
		# include all flavors.
		response['result']['flavors'] = filter(
			lambda flavor: not filter_by or filter_by in flavor.get_keys().keys(),
			nova_connection().flavors.list())
	except Exception:
		# error communicating with openstack
		response['response'] = "error"
		response['result']['message'] = "Error communicating with OpenStack cluster."
	return response

def flavor_error_response(message, flavor=None):
	# response
	response['response'] = "error"
	response['result']['flavor'] = row2dict(flavor)
	response['result']['message'] = "%s" % message
	
	# disable flavor	
	flavor.osid = ""
	flavor.active = 0
	flavor.update()

	# log it
	app.logger.error("Failed to install flavor=(%s) into the OpenStack cluster. %s" % (flavor.name, message))

	return response

def flavor_uninstall(flavor):
	response = {"response": "error", "result": {"message": ""}}
	# establish connection to openstack
	try:
		osflavor = nova_connection().flavors.get(flavor.osid)
		if not osflavor:
			response['response'] = "error"
			response['result']['messge'] = "Failed to get flavor."
		else:
			osflavor.delete()
	except nova_exceptions.Forbidden:
		response['response'] = "forbidden"
		response['result']['message'] = "Forbidden to delete flavor due to lack of permissions."
		return response
	except Exception as ex:
		response['response'] = "error"
		response['result']['messge'] = str(ex)
	return {"response": "success"}

# used by instance start method to install a flavor if we don't have it
# or re-install a flavor if the flavor doesn't match appliance specs
def flavor_verify_install(flavor):
	# build the response
	response = {"response": "", "result": {"message": "", "flavor": {}}}

	# get the cluster configuration
	try:
		openstack = db.session.query(OpenStack).first()
		
		# what happens if they haven't configured it already?
		if not openstack:
			raise OpenStackConfiguration("OpenStack configuration isn't complete.")
	except Exception as ex:
		# return error
		flavor_error_response(ex)
	
	# establish connection to openstack
	try:
		nova = nova_connection()
	except Exception as ex:
		# return error
		flavor_error_response(ex)

	# look up flavors		
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

	# check flavor specs match
	if targetflavor:
		if targetflavor.vcpus != flavor.vpus: # vpus wrong
			install_flavor = True
		if targetflavor.disk != flavor.disk: # disk size wrong
			install_flavor = True 
		if targetflavor.ram != flavor.memory: # memory wrong
			install_flavor = True

		try: 
			# get the flavor network quota keys and check quotas match
			osikeys = targetflavor.get_keys()
			if flavor.network_up > 0:
				if 'quota:outbound_average' not in osikeys or \
						flavor.network_up != int(osikeys['quota:outbound_average']):
					install_flavor = True
			if flavor.network_down > 0:
				if 'quota:inbound_average' not in osikeys or \
						flavor.network_down != int(osikeys['quota:inbound_average']):
					install_flavor = True
		except:
			# just force install
			install_flavor = True

	else:
		# no flavor found
		install_flavor = True
		app.logger.info("Flavor not found.")

	# install the flavor
	if install_flavor:
		if targetflavor:
			try:
				# remove the old flavor
				nova.flavors.delete(targetflavor.id)
			except:
				app.logger.info("Could not remove the old flavor=(%s) from the OpenStack cluster." % flavor.name)

		try:
			# referenced from ticket #80 
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
		except nova_exceptions.Forbidden:
			response['response'] = "forbidden"
			response['result']['message'] = "Forbidden to create flavor due to lack of permissions."
			return response
		except:
			response['response'] = "error"
			response['result']['message'] = "Error creating flavor inside OpenStack."
			return response

		# set bandwidth
		targetflavor.set_keys({"quota:inbound_average": flavor.network_down})
		targetflavor.set_keys({"quota:outbound_average": flavor.network_up})

		app.logger.info("Installed flavor=(%s) into the OpenStack cluster." % flavor.name)

	# update the flavor database with id
	flavor.osid = targetflavor.id
	flavor.update(flavor)

	# response
	response['response'] = "success"
	response['result']['message'] = "Flavor added."
	response['result']['flavor'] = row2dict(flavor)

	return response

def get_flavor_keys(os_flavor_id):
	return nova_connection().flavors.get(os_flavor_id).get_keys()

def set_flavor_ask_price(os_flavor_id, ask_price):
	# attempt to update the flavor price on openstack
	nova_connection().flavors.get(os_flavor_id).set_keys(
		{"stackmonkey:ask_price": ask_price})

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
		console = nova.servers.get_console_output(instance.osid, 1000)
	
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


def try_associate_floating_ip(instance):
	# build the response
	response = {"response": "unchanged", "result": {"message": ""}}

	try:
		nova = nova_connection()

		# if instance already has a floating IP we can return
		try:
			nova.floating_ips.find(instance_id=instance.id)
			return response

		# instance has no floating ip yet
		except nova_exceptions.NotFound:
			pass

		# check for already created but not associated floating ips
		unassociated_fips = [
			ip
			for ip in nova.floating_ips.list()
			if ip.instance_id == None
		]

		# if there are no unassociated floating ips we need to create one
		if len(unassociated_fips) < 1:

			# we won't try to create a floating ip pool ourselves if none exists
			if len(nova.floating_ip_pools.list()) < 1:
				response['response'] = "error"
				response['result']['message'] = "There is no floating IP pool available."
				return response

			# try allocating an ip in each of the pools until one succeeds
			for pool in nova.floating_ip_pools.list():
				try:
					unassociated_fips.append(
						nova.floating_ips.create(pool=pool.name))
					break
				except:
					pass

				# still have no floating ip, giving up
				if len(unassociated_fips) < 1:
					response['response'] = "error"
					response['result']['message'] = 'Failed to allocate a new floating IP.'
					return response

		try:
			# associate the first unassociated floating ip to the server
			instance.add_floating_ip(unassociated_fips[0])
			response['response'] = "success"
			response['result']['message'] = 'Floating IP address assigned.'			
			response['result']['ip'] = unassociated_fips[0].ip
		except:
			response['response'] = "error"
			response['result']['message'] = 'Failed to associate floating IP.'
			return response
	except:
		response['response'] = "error"
		response['result']['message'] = "Can't communicate with OpenStack cluster."

	return response
