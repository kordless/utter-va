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
  created INTEGER NOT NULL,
  updated INTEGER NOT NULL,
  osid VARCHAR(100),
  description VARCHAR(200) NOT NULL,
  name VARCHAR(100) NOT NULL,
  url VARCHAR(1024) NOT NULL,
  local_url VARCHAR(1024),
  diskformat VARCHAR(100) NOT NULL,
  containerformat VARCHAR(100) NOT NULL,
  size INTEGER NOT NULL,
  cache INTEGER NOT NULL,
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
  hot INTEGER NOT NULL,
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
  subdomain VARCHAR(100) NOT NULL,
  instance_id INTEGER,
  PRIMARY KEY (id),
  FOREIGN KEY(instance_id) REFERENCES instances(id)
);

DROP TABLE IF EXISTS instances;
CREATE TABLE instances (
  id INTEGER NOT NULL,
  created INTEGER NOT NULL,
  updated INTEGER NOT NULL,
  expires INTEGER NOT NULL,
  name VARCHAR(100) NOT NULL,
  osid VARCHAR(100),
  privateipv4 VARCHAR(100),
  publicipv4 VARCHAR(100),
  publicipv6 VARCHAR(100),
  ssltunnel VARCHAR(400),
  state INTEGER NOT NULL,
  callback_url VARCHAR(1024),
  dynamic_image_url VARCHAR(1024),
  post_creation VARCHAR(8192),
  flavor_id INTEGER NOT NULL,
  image_id INTEGER NOT NULL,
  address_id VARCHAR(100),
  PRIMARY KEY (id),
  FOREIGN KEY(flavor_id) REFERENCES flavors(id),
  FOREIGN KEY(image_id) REFERENCES images(id),
  FOREIGN KEY(address_id) REFERENCES addresses(id)
);

DROP TABLE IF EXISTS status;
CREATE TABLE status (
  id INTEGER NOT NULL,
  updated INTEGER NOT NULL,
  openstack_check INTEGER NOT NULL,
  coinbase_check INTEGER NOT NULL,
  ngrok_check INTEGER NOT NULL,
  flavors_check INTEGER NOT NULL,
  images_check INTEGER NOT NULL,
  token_check INTEGER NOT NULL,
  PRIMARY KEY (id)
);