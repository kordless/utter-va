import os
from subprocess import Popen
from keystoneclient.v2_0 import client as keyclient
from novaclient.v1_1 import client as novaclient
from webapp.configure.models import OpenStack, Appliance
from webapp.api.models import Flavors, Images
from webapp import app, db

def openstack_auth_check(openstack):
	keystone = keyclient.Client(
		username = openstack.osusername,
		password = openstack.ospassword,
		tenant_id = openstack.tenantid,
		auth_url = openstack.authurl
	)
	if not keystone.auth_token:
		raise "fail on aquiring Openstack credentials."

	return

def image_install(image):
	# get the cluster configuration and check we are good to talk to openstack
	openstack = db.session.query(OpenStack).first()
	openstack_auth_check(openstack)
	
	# this is hackish bullshit, but I couldn't figure out how to get the
	# proper service URL for glance.  using command line version instead.
	Popen(["glance", 
		"--os-username", openstack.osusername,
		"--os-password", openstack.ospassword,
		"--os-auth-url", openstack.authurl,
		"--os-tenant-id", openstack.tenantid,
		"image-create",
		"--location", image.url,
		"--disk-format", image.diskformat,
		"--container-format", image.containerformat,
		"--name", image.name
	])
	
	image.active = 1
	image.update(image)
	return image

def image_remove(image):
	# get the cluster configuration
	openstack = db.session.query(OpenStack).first()
	nova = novaclient.Client(openstack.osusername, openstack.ospassword, openstack.tenantname, openstack.authurl, service_type="compute")

	# delete the selected image
	nova.images.delete(image.osid)

	# udpate the images db to reflect
	image.osid = ""
	image.active = 0

	return image

def image_detail(image):
	# establish connection to openstack
	openstack = db.session.query(OpenStack).first()
	nova = novaclient.Client(openstack.osusername, openstack.ospassword, openstack.tenantname, openstack.authurl, service_type="compute")

	# what happens if they haven't configured it already?
	if not openstack:
		pass

	# get the new image's id
	for osimage in nova.images.list():
		# if we find a given image which doesn't have the osid set, update
		if osimage.name == image.name:
			image.osid = osimage.id
			image.update(image)
		if osimage.status == "ACTIVE":
			image.active = 2
	
	return image

def flavor_install(flavor):
	# get the cluster configuration
	openstack = db.session.query(OpenStack).first()
	
	# what happens if they haven't configured it already?
	if not openstack:
		pass

	# establish connection to openstack
	nova = novaclient.Client(openstack.osusername, openstack.ospassword, openstack.tenantname, openstack.authurl, service_type="compute")
	
	# create the new flavor
	osflavor = nova.flavors.create(flavor.name, flavor.mem, flavor.vpu, flavor.disk, None, 0, 0, 1.0, True)
	osflavor.set_keys({"provider": app.config["POOL_NAME"]})

	# update the appliance database with id
	flavor.osid = osflavor.id
	flavor.active = 1
	flavor.update(flavor)

	# return the updated flavor
	return flavor

def flavor_remove(flavor):
	openstack = db.session.query(OpenStack).first()
	
	# what happens if they haven't configured it already?
	if not openstack:
		pass
	
	# establish connection to openstack and delete flavor
	nova = novaclient.Client(openstack.osusername, openstack.ospassword, openstack.tenantname, openstack.authurl, service_type="compute")
	osflavor = nova.flavors.delete(flavor.osid)

	# address issue #15 here

	# update our flavor to not be installed
	flavor.osid = ""
	flavor.active = 0
	flavor.update(flavor)

	# return
	return flavor

def flavors_installed():
	# get the cluster configuration
	openstack = db.session.query(OpenStack).first()
	
	# what happens if they haven't configured it already?
	if not openstack:
		pass

	# establish connection to openstack
	nova = novaclient.Client(openstack.osusername, openstack.ospassword, openstack.tenantname, openstack.authurl, service_type="compute")
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