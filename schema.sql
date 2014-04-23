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

DROP TABLE IF EXISTS addresses;
CREATE TABLE addresses (
  id INTEGER NOT NULL,
  address VARCHAR(100) NOT NULL,
  token VARCHAR(100) NOT NULL,
  instanceid INTEGER,
  subdomain VARCHAR(100) NOT NULL,
  PRIMARY KEY (id)
);

DROP TABLE IF EXISTS instances;
CREATE TABLE instances (
  id INTEGER NOT NULL,
  created INTEGER NOT NULL,
  updated INTEGER NOT NULL,
  expires INTEGER NOT NULL,
  name VARCHAR(100) NOT NULL,
  osid VARCHAR(100),
  poolid VARCHAR(100),
  flavor INTEGER NOT NULL,
  image INTEGER NOT NULL,
  privateipv4 VARCHAR(100),
  publicipv4 VARCHAR(100),
  publicipv6 VARCHAR(100),
  ssltunnel VARCHAR(400),
  state INTEGER NOT NULL,
  sshkey VARCHAR(2048),
  PRIMARY KEY (id)
);