import os

from urllib2 import urlopen, urlretrieve

# download images, store locally in static/images & update images db
# NOTE: this is a blocking call, and for use from ./manage.py only
def download_images(appliance, images):
	# image path for this appliance
	image_path = "%s/../static/images" % os.path.dirname(os.path.abspath(__file__))
		
	# loop through images and try to download and install
	for image in images:
		# backup the original url
		original_url = image.url

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
				
				# update the database saying we have the file
				image.size = size
				image.active = 3

				# write the new URL for the image
				if app.config['DEBUG'] == True:
					image.url = "http://%s:%s/images/%s" % (
						appliance.local_ip, 
						app.config['DEV_PORT'],
						filename
					)
				else:
					image.url = "http://%s/images/%s" % (
						appliance.local_ip,
						filename
					)

				image.update()

			else:
				# do nothing if we already have it locally
				image.size = on_disk_size
				image.active = 3
				image.update()

		except Exception, e:
			# reset the URL so OpenStack can download it directly
			image.url = original_url
			image.active = 1
			image.update()

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
			return True
	except:
		return False