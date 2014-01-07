DROP TABLE IF EXISTS users;
CREATE TABLE users (
  id INTEGER NOT NULL,
  username VARCHAR(50) NOT NULL,
  password VARCHAR(100) NOT NULL,
  email VARCHAR(100),
  accountid VARCHAR(32),
  PRIMARY KEY (id)
);
