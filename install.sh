#!/bin/bash

# name: install.sh
# description: install script for stackmonkey controller vm
# author: info@stackmonkey.com 
# github: https://github.com/StackMonkey/stackmonkey-vm

# update repos
sudo apt-get update -y

# install dependencies and services
sudo apt-get install git -y
sudo apt-get install python-pip -y
sudo apt-get install libapache2-mod-wsgi -y
sudo apt-get install build-essential -y
sudo apt-get install python-dev -y
sudo apt-get install python-virtualenv -y

# install werkzeug
sudo pip install Werkzeug

# install flask bits via pip
sudo pip install flask
sudo pip install flask-wtf
sudo pip install flask-appconfig
sudo pip install flask-login
sudo pip install flask-openid
sudo pip install flask-sqlalchemy

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

    WSGIDaemonProcess stackmonkey user=www-data group=www-data threads=5
    WSGIScriptAlias / /var/www/stackmonkey/wsgi.py

    <Directory /var/www/stackmonkey>
        WSGIScriptReloading On
        WSGIProcessGroup stackmonkey
        WSGIApplicationGroup %{GLOBAL}
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
sudo git clone https://github.com/StackMonkey/stackmonkey-vm.git stackmonkey
 
# configure www directory
sudo chown -R www-data:www-data /var/www/

# restart apache
sudo service apache2 restart
