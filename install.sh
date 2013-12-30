#!/bin/bash

# name: install.sh
# description: install script for stackmonkey controller vm
# author: info@stackmonkey.com 
# github: https://github.com/StackMonkey/stackmonkey-vm

# update repos
sudo apt-get update -y

# install git and pip
sudo apt-get install git -y
sudo apt-get install python-pip -y

# install service and dependencies
sudo apt-get install build-essential -y
sudo apt-get install python-dev -y
sudo apt-get install nginx -y
sudo apt-get install uwsgi -y
sudo apt-get install uwsgi-plugin-python -y

# configure www directory
sudo mkdir -p /var/www/stackmonkey/static
sudo usermod -a -G www-data www-data
sudo chown -R www-data:www-data /var/www/
sudo chmod -R g+w /var/www/stackmonkey/

# install virtual environment 
sudo pip install virtualenv

# configure virtual environment
cd /var/www/stackmonkey/
sudo virtualenv ./env
sudo source env/bin/activate

# install flask bits via pip
sudo pip install Flask
sudo pip install flask-wtf
sudo pip install flask-appconfig
sudo pip install flask-bootstrap

# install openstack libraries for python
sudo pip install python-keystoneclient
sudo pip install python-glanceclient
sudo pip install python-cinderclient
sudo pip install python-novaclient

# exit env
sudo deactivate

# configure nginx
sudo cat <<EOF > /etc/nginx/site-available/default
server {
    listen       80;
    server_name  stackmonkey;

    location /static {
        alias /var/www/stackmonkey/static;
    }

    location / {
        include uwsgi_params;
        uwsgi_pass unix:/tmp/stackmonkey.sock;
        uwsgi_param UWSGI_PYHOME /var/www/stackmonkey/env;
        uwsgi_param UWSGI_CHDIR /var/www/stackmonkey;
        uwsgi_param UWSGI_MODULE application;
        uwsgi_param UWSGI_CALLABLE app;
    }

    error_page   404              /404.html;

    error_page   500 502 503 504  /50x.html;
    location = /50x.html {
        root   /usr/share/nginx/www;
    }
}
EOF
sudo ln -s /etc/nginx/sites-available/stackmonkey /etc/nginx/sites-enabled/stackmonkey

# setup uwsgi
sudo cat <<EOF > /etc/uwsgi/apps-available/stackmonkey.ini
[uwsgi]
plugins=python
vhost=true
socket=/tmp/stackmonkey.sock
EOF
sudo ln -s /etc/uwsgi/apps-available/website.ini /etc/uwsgi/apps-enabled/website.ini

# restart services
sudo service uwsgi restart
sudo service nginx restart

# check out stackgeek-vm repo
sudo su
cd /root/
sudo git clone https://github.com/StackMonkey/stackmonkey-vm.git
