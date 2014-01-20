#!/bin/bash

# name: install.sh
# description: install script for xovio controller vm
# compute-pool: stackmonkey.com
# author: info@xovio.com 
# github: https://github.com/StackMonkey/xovio-va

# service token generation
SERVICE_ENDPOINT_HOSTAME=`/usr/bin/openssl rand -hex 16`
API_TOKEN=`/usr/bin/openssl rand -hex 64`

# update repos
sudo apt-get update -y

# install dependencies and services
sudo apt-get install git -y
sudo apt-get install sqlite3 -y
sudo apt-get install python-pip -y
sudo apt-get install libapache2-mod-wsgi -y
sudo apt-get install build-essential -y
sudo apt-get install python-dev -y
sudo apt-get install python-virtualenv -y
sudo apt-get install unzip -y
sudo apt-get install monit -y

# install ngrok
sudo wget -qO /tmp/ngrok.zip https://dl.ngrok.com/linux_386/ngrok.zip
sudo unzip /tmp/ngrok.zip
sudo mv ngrok /usr/local/bin/ngrok

# install werkzeug
sudo pip install Werkzeug

# install flask bits via pip
sudo pip install flask
sudo pip install flask-wtf
sudo pip install flask-appconfig
sudo pip install flask-login
sudo pip install flask-openid
sudo pip install flask-sqlalchemy
sudo pip install flask-actions
sudo pip install flask-bcrypt

# install openstack libraries for python
sudo pip install python-keystoneclient
sudo pip install python-glanceclient
sudo pip install python-cinderclient
sudo pip install python-novaclient

# configure apache
mkdir /var/log/stackmonkey/
chown -R www-data:www-data /var/log/stackmonkey/
sudo cat <<EOF > /etc/apache2/sites-available/default
<VirtualHost *:80>
    ServerName controller.stackmonkey.com

    Alias /img/ "/var/www/stackmonkey/webapp/static/img/"
    Alias /css/ "/var/www/stackmonkey/webapp/static/css/"
    Alias /js/ "/var/www/stackmonkey/webapp/static/js/"
    Alias /fonts/ "/var/www/stackmonkey/webapp/static/fonts/"

    <Directory /var/www/stackmonkey/webapp/static>
        Order deny,allow
        Allow from all
    </Directory>

    WSGIDaemonProcess stackmonkey user=www-data group=www-data threads=5
    WSGIScriptAlias / /var/www/stackmonkey/wsgi.py

    <Directory /var/www/stackmonkey>
        WSGIProcessGroup stackmonkey
        WSGIApplicationGroup %{GLOBAL}
        WSGIScriptReloading On
        Order deny,allow
        Allow from all
    </Directory>

    LogLevel warn
    ErrorLog /var/log/stackmonkey/error.log
    CustomLog /var/log/stackmonkey/access.log combined
</VirtualHost>
EOF

# check out stackgeek-vm repo
sudo su
cd /var/www/
sudo git clone https://github.com/StackMonkey/xovio-va.git stackmonkey

# setup token config
sudo cat <<EOF > /var/www/stackmonkey/tokens.py
    API_TOKEN = "$API_TOKEN"
    SERVICE_ENDPOINT_HOSTAME = "$SERVICE_ENDPOINT_HOSTAME"
    NGROK_TOKEN = "$NGROK_TOKEN"
EOF

# build the database and sync with stackmonkey.com
su www-data
cd /var/www/stackmonkey/
/var/www/stackmonkey/manage.py resetdb  # FIX THIS SHIT
/var/www/stackmonkey/manage.py sync
/var/www/stackmonkey/manage.py insert tokens

# configure www directory
sudo chown -R www-data:www-data /var/www/

# restart apache
sudo service apache2 restart
