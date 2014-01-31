import os
from subprocess import Popen
from novaclient.v1_1 import client as novaclient
from keystoneclient.v2_0 import client as keyclient
from webapp import app, db
from webapp.configure.models import OpenStack, Appliance
from webapp.api.models import Flavors, Images
from webapp.libs.exceptions import OpenStackConfiguration

def openstack_auth_check():
	# get the cluster configuration and check we are good to talk to openstack
	openstack = db.session.query(OpenStack).first()

	if openstack:
		try:
			keystone = keyclient.Client(
				username = openstack.osusername,
				password = openstack.ospassword,
				tenant_id = openstack.tenantid,
				auth_url = openstack.authurl
			)
		except:
			return False
	else:
		return False
	
	return True
	
def image_install(image):
	try:
		# try doing an auth
		if not openstack_auth_check():
			raise OpenStackConfiguration("OpenStack configuration isn't complete.")
		
		# get openstack credentials
		openstack = db.session.query(OpenStack).first()

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

# complement function for image_install above as glance command doesn't 
# return any data we can use to populate the image database locally.
def image_detail(image):
	try:
		# establish connection to openstack
		openstack = db.session.query(OpenStack).first()
		
		# what happens if they haven't configured it already?
		if not openstack:
			raise OpenStackConfiguration("OpenStack configuration isn't complete.")

		# connect to nova 
		nova = novaclient.Client(openstack.osusername, openstack.ospassword, openstack.tenantname, openstack.authurl, service_type="compute")

		# get the new image's id
		for osimage in nova.images.list():
			# if we find a given image which doesn't have the osid set, update
			if osimage.name == image.name:
				image.osid = osimage.id
				image.update(image)
			# if we see the image go active, indicate
			if osimage.status == "ACTIVE":
				image.active = 2
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

def images_cleanup():
	# get the cluster configuration
	openstack = db.session.query(OpenStack).first()
	
	# what happens if they haven't configured it already?
	if not openstack:
		pass

	# establish connection to openstack
	nova = novaclient.Client(openstack.osusername, openstack.ospassword, openstack.tenantname, openstack.authurl, service_type="compute")
	osimages = nova.images.list()

	# get list of currently known images
	images = db.session.query(Images).all()

	# create the results template
	results = {'response': 'success', 'images': []}

	# there's got to be a better way...probably with a generator
	# images in appliance database
	for image in images:
		# set this images to be not installed until we find out otherwise
		install_flag = False

		# images coming from OpenStack
		for osimage in osimages:
			if image.osid == osimage.id:
				# indicated this is installed and active
				image_iter = db.session.query(Images).filter_by(id=image.id).first()
				results['images'].append({"id": image.id, "active": 2})
				install_flag = True
				image_iter.active = 2
				image_iter.update(image_iter)

			elif image.name == osimage.name:
				# if image names match, but osimage.id does not, populate osid
				# this happens if the image is already installed & we don't know about it
				image_iter = db.session.query(Images).filter_by(id=image.id).first()
				image_iter.osid = osimage.id
				image_iter.active = 1
				image_iter.update(image_iter)
				results['images'].append({"id": image.id, "active": 1})
				install_flag = True

		if not install_flag:
			# clear this entry's id while we're here cause it's not installed
			image_iter = db.session.query(Images).filter_by(id=image.id).first()
			image_iter.osid = ""
			image_iter.active = 0
			image_iter.update(image_iter)
			results['images'].append({"id": image.id, "active": 0})

	return results

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
		osflavor = nova.flavors.create(flavor.name, flavor.mem, flavor.vpu, flavor.disk, None, 0, 0, 1.0, True)
		osflavor.set_keys({"provider": app.config["POOL_NAME"]})

		# update the appliance database with id
		flavor.osid = osflavor.id
		flavor.active = 1
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

def flavors_cleanup():
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

	# create the results template
	results = {'response': 'success', 'flavors': []}

	# there's got to be a better way...probably with a generator
	# flavors in appliance database
	for flavor in flavors:
		# set this flavor to be not installed until we find out otherwise
		install_flag = False

		# flavors coming from OpenStack
		for osflavor in osflavors:
			if flavor.osid == osflavor.id:
				# indicated this is installed and active
				results['flavors'].append({"id": flavor.id, "state": "active"})
				install_flag = True
			elif flavor.name == osflavor.name:
				# if flavor names match, but osflavor.id does not, populate osid
				# this happens if the flavor is already installed & we don't know about it
				flavor_iter = db.session.query(Flavors).filter_by(id=flavor.id).first()
				flavor_iter.osid = osflavor.id
				flavor_iter.active = 1
				flavor_iter.update(flavor_iter)
				results['flavors'].append({"id": flavor.id, "state": "active"})
				install_flag = True

		if not install_flag:
			# clear this entry's id while we're here cause it's not installed
			flavor_iter = db.session.query(Flavors).filter_by(id=flavor.id).first()
			flavor_iter.osid = ""
			flavor_iter.active = 0
			flavor_iter.update(flavor_iter)
			results['flavors'].append({"id": flavor.id, "state": 0})

	return results

def start_instance():
	pass

def terminate_instance():
	pass