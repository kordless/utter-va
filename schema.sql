DROP TABLE IF EXISTS users;
CREATE TABLE users (
  id INTEGER NOT NULL,
  username VARCHAR(100) NOT NULL,
  password VARCHAR(100) NOT NULL,
  PRIMARY KEY (id)
);

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

DROP TABLE IF EXISTS appliance;
CREATE TABLE appliance (
  id INTEGER NOT NULL,
  apitoken VARCHAR(100) NOT NULL,
  ngroktoken VARCHAR(100),
  subdomain VARCHAR(100),
  dynamicimages INTEGER NOT NULL,
  secret VARCHAR(100),
  cbapikey VARCHAR(100),
  cbapisecret VARCHAR(100),
  latitude VARCHAR(100) NOT NULL,
  longitude VARCHAR(100) NOT NULL,
  local_ip VARCHAR(100) NOT NULL,
  PRIMARY KEY (id)
);

DROP TABLE IF EXISTS images;
CREATE TABLE images (
  id INTEGER NOT NULL,
  osid VARCHAR(100),
  description VARCHAR(200) NOT NULL,
  name VARCHAR(100) NOT NULL,
  url VARCHAR(400) NOT NULL,
  diskformat VARCHAR(100) NOT NULL,
  containerformat VARCHAR(100) NOT NULL,
  size INTEGER NOT NULL,
  active INTEGER NOT NULL,
  flags INTEGER NOT NULL,
  PRIMARY KEY (id)  
);

DROP TABLE IF EXISTS flavors;
CREATE TABLE flavors (
  id INTEGER NOT NULL,
  osid VARCHAR(100),
  name VARCHAR(100) NOT NULL,
  description VARCHAR(200) NOT NULL,
  vpus INTEGER NOT NULL,
  memory INTEGER NOT NULL,
  disk INTEGER NOT NULL,
  network INTEGER NOT NULL,
  rate INTEGER NOT NULL,
  ask INTEGER NOT NULL,
  launches INTEGER NOT NULL,
  active INTEGER NOT NULL,
  flags INTEGER NOT NULL,
  PRIMARY KEY (id)  
);

DROP TABLE IF EXISTS instances;
CREATE TABLE instances (
  id INTEGER NOT NULL,
  created INTEGER NOT NULL,
  updated INTEGER NOT NULL,
  expires INTEGER NOT NULL,
  osflavorid INTEGER NOT NULL,
  osimageid INTEGER NOT NULL,
  publicipv4 VARCHAR(100) NOT NULL,
  publicipv6 VARCHAR(100) NOT NULL,
  ssltunnel VARCHAR(400) NOT NULL,
  osinstanceid VARCHAR(100),
  name VARCHAR(100) NOT NULL,
  state INTEGER NOT NULL,
  token VARCHAR(100) NOT NULL,
  address VARCHAR(100) NOT NULL,
  hourlyrate INTEGER NOT NULL,
  PRIMARY KEY (id)
);