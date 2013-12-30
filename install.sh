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
sudo apt-get install nginx -y
sudo apt-get install build-essential -y
sudo apt-get install python-dev -y
sudo pip install uwsgi 

# configure user settings
sudo useradd -c 'uwsgi user,,,' -g www-data -d /nonexistent -s /bin/false uwsgi

# configure www directory
sudo mkdir -p /var/www/stackmonkey/
sudo usermod -a -G www-data www-data
sudo chown -R www-data:www-data /var/www/
sudo chmod -R g+w /var/www/stackmonkey/

# configure uwsgi configs
sudo cat <<EOF > /etc/init/uwsgi.conf
description "uWSGI"
start on runlevel [2345]
stop on runlevel [06]

respawn

exec uwsgi --master --processes 4 --die-on-term --uid uwsgi --gid www-data --socket /tmp/uwsgi.sock --chmod-socket 660 --no-site --vhost --logto /var/log/uwsgi.log
EOF

# set up logging for uwsgi
sudo cat <<EOF > /etc/logrotate.d/uwsgi
/var/log/uwsgi.log {
    rotate 10
    daily
    compress
    missingok
    create 640 uwsgi adm
    postrotate
        initctl restart uwsgi >/dev/null 2>&1
    endscript
}
EOF

sudo touch /var/log/uwsgi.log
sudo logrotate -f /etc/logrotate.d/uwsgi

# configure nginx
sudo cat <<EOF > /etc/nginx/conf.d/stackmonkey.conf
server {
    listen       80;
    server_name  stackmonkey;

    location /static {
        alias /var/www/stackmonkey/static;
    }

    location / {
        include uwsgi_params;
        uwsgi_pass unix:/tmp/uwsgi.sock;
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

# restart services
sudo service uwsgi restart
sudo service nginx restart

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


# check out stackgeek-vm repo
sudo su
cd /root/
sudo git clone https://github.com/StackMonkey/stackmonkey-vm.git
