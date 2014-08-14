import sqlite3
from novaclient.v1_1 import client as novaclient
from cinderclient import client as cclient
import keystoneclient.v2_0.client as ksclient
import glanceclient

"""
DROP TABLE IF EXISTS openstack;
CREATE TABLE openstack (
  id INTEGER NOT NULL,
  authurl VARCHAR(100) NOT NULL,
  tenantname VARCHAR(100) NOT NULL,
  tenantid VARCHAR(100) NOT NULL,
  osusername VARCHAR(100) NOT NULL,
  ospassword VARCHAR(100),
  PRIMARY KEY (id)
);
"""

# connect to db and fetch info
c = sqlite3.connect('../utterio.db')
foo = c.execute('select * from openstack')
result = foo.fetchone()

# establish connection to openstack nova
connection = novaclient.Client(
	result[4], # username
	result[5], # password
	result[2], # tenant name
	result[1], # auth URL
	service_type="compute"
)

# proper way of getting glance image via python
keystone = ksclient.Client(
	auth_url = result[1], 
	username = result[4], 
	password = result[5], 
	tenant_id = result[3]
)

# grab glance endpoint from keystone
glance_endpoint = keystone.service_catalog.url_for(service_type='image')

# start connection to glance
glance = glanceclient.Client('1', endpoint=glance_endpoint, token=keystone.auth_token)

# get images
osimages = glance.images.list()

print osimages.next()