#!/usr/bin/python
# manage.py
# -*- encoding:utf-8 -*-
import os, sys, socket, json
from urllib2 import urlopen
from flask import Flask
from flaskext.actions import Manager
from webapp import app, db
from webapp.configure.models import OpenStack, Appliance
from webapp.api.models import Images, Flavors
from webapp.users.models import User
from webapp.libs.controlserver import check_version, get_images, get_flavors

app.config.from_object('config.DebugConfiguration') # configuration
manager = Manager(app, default_help_actions=False)

def configure_blurb():
	hostname = socket.gethostname()
	IP = socket.gethostbyname(hostname)
	print "Visit http://%s/ to setup your appliance before running this command." % IP

def server_connect( method = "version" ):
	appliance = db.session.query(Appliance).first()
	url = app.config['APP_WEBSITE'] + 'api/%s?ver=' % method + app.config['VERSION'] + '&apitoken=' + appliance.apitoken
	response = urlopen(url, timeout=10).read()
	return json.loads(response)

def sync(app):
	def action():
		# check version of virtual appliance
		version = False
		try:
			version = server_connect( method = "version" )
		except AttributeError as ex:
			configure_blurb()
		except IOError as ex:
			print "Can't contact central server.  Try again later."
		except ValueError as ex:
			print "Having issues parsing JSON from the site: %s.  Open a ticket." % type(ex).__name__
		except Exception as ex:
			print "An error of type %s has occured.  Open a ticket." % type(ex).__name__
		
		if not version:
			return action
		
		# update list of current images in db
		remoteimages = False
		try:
			remoteimages = server_connect("images")
		except AttributeError as ex:
			configure_blurb()
		except IOError as ex:
			print "Can't contact central server.  Try again later."
		except ValueError as ex:
			print "Having issues parsing JSON from the site: %s.  Open a ticket." % type(ex).__name__
		except Exception as ex:
			print "An error of type %s has occured.  Open a ticket." % type(ex).__name__

		if not remoteimages:
			return action

		# update the database with the images
		for remoteimage in remoteimages['images']:
			image = db.session.query(Images).filter_by(md5=remoteimage['md5']).first()
			if image is None:
				# we don't have the image coming in from the server
				image = Images()

				# need help here populating db object from dict - anyone?
				image.md5 = remoteimage['md5']
				image.name = remoteimage['name']
				image.url = remoteimage['url']
				image.size = remoteimage['size']
				image.flags = remoteimage['flags']
				image.installed = 0

				# add and commit
				db.session.add(image)
				db.session.commit()
			else:
				# we have the image already, so update
				# need help here populating db object from dict - anyone?
				# hey, it's a fucking POC, alright?
				image.md5 = remoteimage['md5']
				image.name = remoteimage['name']
				image.url = remoteimage['url']
				image.size = remoteimage['size']
				image.flags = remoteimage['flags']
				
				# udpate and commit
				image.update(image)
				db.session.commit()

		# update list of current flavors in db
		remoteflavors = False
		try:
			remoteflavors = server_connect("flavors")
		except AttributeError as ex:
			configure_blurb()
		except IOError as ex:
			print "Can't contact central server.  Try again later."
		except ValueError as ex:
			print "Having issues parsing JSON from the site: %s.  Open a ticket." % type(ex).__name__
		except Exception as ex:
			print "An error of type %s has occured.  Open a ticket." % type(ex).__name__

		if not remoteflavors:
			return action

		# update the database with the flavors
		for remoteflavor in remoteflavors['flavors']:
			flavor = db.session.query(Flavors).filter_by(name=remoteflavor['name']).first()
			if flavor is None:
				# we don't have the flavor coming in from the server
				flavor = Flavors()

				# need help here populating db object from dict - anyone?
				flavor.name = remoteflavor['name']
				flavor.comment = remoteflavor['comment']
				flavor.vpu = remoteflavor['vpu']
				flavor.mem = remoteflavor['mem']
				flavor.disk = remoteflavor['disk']
				flavor.flags = remoteflavor['flags']
				flavor.installed = 0

				# add and commit
				db.session.add(flavor)
				db.session.commit()
			else:
				# we have the flavor already, so update
				# need help here populating db object from dict - anyone?
				flavor.name = remoteflavor['name']
				flavor.comment = remoteflavor['comment']
				flavor.vpu = remoteflavor['vpu']
				flavor.mem = remoteflavor['mem']
				flavor.disk = remoteflavor['disk']
				flavor.flags = remoteflavor['flags']
				
				# udpate and commit
				flavor.update(flavor)
				db.session.commit()

	return action

def resetdb(app):
	def action():
		os.system('./resetdb.sh')
		print "Database reset."
	return action

def ngrok(app):
	def action():
		appliance = db.session.query(Appliance).first()
		os.system('./resetdb.sh %s %s %s' % (appliance.ngroktoken, appliance.serviceurl, appliance.apitoken))
		os.system('service monit restart')
		print "Database reset."
	return action

def serve(app):
	def action():
		from werkzeug import SharedDataMiddleware

		# add static directory to be served by development server
		app.wsgi_app = SharedDataMiddleware(app.wsgi_app, {'/': os.path.join(os.path.dirname(__file__), './webapp/static') })
		app.run(debug=True, host="0.0.0.0")
		sys.exit()
	return action


manager.add_action('sync', sync)
manager.add_action('resetdb', resetdb)
manager.add_action('serve', serve)

if __name__ == "__main__":
    manager.run()
