import os
import time

from webapp import app

from urllib2 import urlopen
from urllib import urlretrieve

# download images, store locally in static/images & update images db
# NOTE: this is a blocking call, and for use from ./manage.py only
def download_images(appliance, images):
	# image path for this appliance
	image_path = "%s/../static/images" % os.path.dirname(os.path.abspath(__file__))
		
	# loop through images and try to download and install
	for image in images:
		try:
			# connect to remote URL's site and get size
			site = urlopen(image.url)
			meta = site.info()
			size = int(meta.getheaders("Content-Length")[0])
			site.close()

			# build filename
			filename = image.url.split('/')[-1]

			# check if we have a file that size/name already
			try:
				on_disk_size = int(os.stat("%s/%s" % (image_path, filename)).st_size)
			except:
				on_disk_size = 0

			# if local disk size not equal to remote size, download it
			# TODO: this should be optimized to verify file integrity
			if on_disk_size != int(size):				
				# mark image as installing
				image.active = 2
				image.update()

				# pull down file and write to disk
				urlretrieve(image.url, "%s/%s" % (image_path, filename))

				# update the new size
				image.size = size
				epoch_time = int(time.time())
				image.updated = epoch_time
				
			else:
				# basically do nothing if we already have it locally
				app.logger.info("Local image=(%s) with size=(%s) is the current version." % (image.name, image.size))
				image.size = on_disk_size
				
			# either way, write the local URL for the image
			if app.config['DEBUG'] == True:
				image.local_url = "http://%s:%s/images/%s" % (
					appliance.local_ip, 
					app.config['DEV_PORT'],
					filename
				)
			else:
				image.local_url = "http://%s/images/%s" % (
					appliance.local_ip,
					filename
				)

			# mark as live on the local filesystem
			image.active = 3
			image.update()

		except Exception, e:
			# we failed to open image.url for size, or failed to download it locally
			# if the local url is empty, indicate we should use original url to boot image
			if image.local_url == "" or image.local_url is None:
				epoch_time = int(time.time())
				image.updated = epoch_time
				image.active = 1
				image.update()
			else:
				# do nothing
				pass

			app.logger.error("Failed to download image from URL.")

# uninstall downloaded images
def uninstall_image(image):
	# image path for this appliance
	image_path = "%s/../static/images" % os.path.dirname(os.path.abspath(__file__))

	# grab existing url and extract filename
	url = image.url
	filename = image.url.split('/')[-1]

	# look for file and size
	try:
		if os.path.isfile("%s/%s" % (image_path, filename)):
			# delete the image
			os.remove("%s/%s" % (image_path, filename))
			app.logger.info("Uninstalled image from file system.")
			return True
	except:
		app.logger.error("Could not find image file to uninstall.")
		return False