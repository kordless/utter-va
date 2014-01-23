import os
from novaclient.v1_1 import client
from webapp.configure.models import OpenStack, Appliance
from webapp.api.models import Flavors, Images
from webapp import app, db

def image_install():
	pass

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

	installed = []

	# flavors in appliance database
	for flavor in flavors:
		# flavors coming from OpenStack
		for osflavor in osflavors:
			install_flag = False
			if flavor.osid == osflavor.id:
				# indicated this is installed
				installed.append({"id": flavor.id, "installed": True})
				install_flag = True
		if not install_flag and flavor.id != "":
			# clear this entry's id
			flavor2 = db.session.query(Flavors).filter_by(id=flavor.id).first()
			flavor2.update(flavor2)

	return installed

def start_instance():
	pass

def terminate_instance():
	pass