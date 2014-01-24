import os
from novaclient.v1_1 import client
from webapp.configure.models import OpenStack, Appliance
from webapp.api.models import Flavors, Images
from webapp import app, db

def image_install():
	pass

def flavor_remove(flavor):
	openstack = db.session.query(OpenStack).first()
	
	# what happens if they haven't configured it already?
	if not openstack:
		pass
	
	# establish connection to openstack and delete flavor
	nova = client.Client(openstack.osusername, openstack.ospassword, openstack.tenantname, openstack.authurl, service_type="compute")
	osflavor = nova.flavors.delete(flavor.osid)

	# update our flavor to not be installed
	flavor.osid = ""
	flavor.active = 0
	flavor.update(flavor)

	# return
	return flavor

def flavor_pause(flavor):
	# update flavor - seems like a bad place for this, but whatever
	flavor.active = 0
	flavor.update(flavor)

	# return
	return flavor

def flavor_install(flavor):
	# get the cluster configuration
	openstack = db.session.query(OpenStack).first()
	
	# what happens if they haven't configured it already?
	if not openstack:
		pass

	# establish connection to openstack
	nova = client.Client(openstack.osusername, openstack.ospassword, openstack.tenantname, openstack.authurl, service_type="compute")
	
	# create the new flavor
	osflavor = nova.flavors.create(flavor.name, flavor.mem, flavor.vpu, flavor.disk, None, 0, 0, 1.0, True)
	osflavor.set_keys({"provider": app.config["POOL_NAME"]})

	# update the appliance database with id
	flavor.osid = osflavor.id
	flavor.active = 1
	flavor.update(flavor)

	# return the updated flavor
	return flavor

def flavors_installed():
	# get the cluster configuration
	openstack = db.session.query(OpenStack).first()
	
	# what happens if they haven't configured it already?
	if not openstack:
		pass

	# establish connection to openstack
	nova = client.Client(openstack.osusername, openstack.ospassword, openstack.tenantname, openstack.authurl, service_type="compute")
	osflavors = nova.flavors.list()

	# get list of currently known flavors
	flavors = db.session.query(Flavors).all()

	results = {'results': []}

	# there's got to be a better way...probably with a generator
	# flavors in appliance database
	for flavor in flavors:
		# flavors coming from OpenStack
		for osflavor in osflavors:
			install_flag = False
			if flavor.osid == osflavor.id:
				# indicated this is installed and active
				results['results'].append({"id": flavor.id, "state": "active"})
				install_flag = True
			elif flavor.name == osflavor.name:
				print "found a match, but not installed"
				# if flavor names match, but osflavor.id does not, populate osid
				# this happens if the flavor is already installed byt we don't know about it
				flavor_iter = db.session.query(Flavors).filter_by(id=flavor.id).first()
				flavor_iter.osid = osflavor.id
				flavor_iter.active = 1
				flavor_iter.update(flavor_iter)
				results['results'].append({"id": flavor.id, "state": "active"})
				install_flag = True

		if not install_flag and flavor.id != "":
			# clear this entry's id while we're here cause it's not installed
			flavor_iter = db.session.query(Flavors).filter_by(id=flavor.id).first()
			flavor_iter.update(flavor_iter)

	return results

def start_instance():
	pass

def terminate_instance():
	pass