#!/bin/bash

# name: install.sh
# description: install script for xovio controller vm
# author: info@xovio.com 
# github: https://github.com/StackMonkey/xovio-va

# pool operator domian
export POOL_URL="stackmonkey.com"
export POOL_SHORT_NAME="stackmonkey"

# update repos
sudo apt-get update -y

# install dependencies and services
sudo apt-get install git -y
sudo apt-get install sqlite3 -y
sudo apt-get install python-pip -y
sudo apt-get install libapache2-mod-wsgi -y
sudo apt-get install build-essential -y
sudo apt-get install python-dev -y
sudo apt-get install unzip -y
sudo apt-get install monit -y

# install pyopenssl
sudo pip install --upgrede pyopenssl

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
sudo mkdir /var/log/xoviova/
sudo chown -R www-data:www-data /var/log/xoviova/
sudo cat <<EOF > /etc/apache2/sites-available/default
<VirtualHost *:80>
    ServerName controller.xov.io

    Alias /img/ "/var/www/xoviova/webapp/static/img/"
    Alias /css/ "/var/www/xoviova/webapp/static/css/"
    Alias /js/ "/var/www/xoviova/webapp/static/js/"
    Alias /fonts/ "/var/www/xoviova/webapp/static/fonts/"

    <Directory /var/www/xoviova/webapp/static>
        Order deny,allow
        Allow from all
    </Directory>

    WSGIDaemonProcess xoviova user=www-data group=www-data threads=5
    WSGIScriptAlias / /var/www/xoviova/wsgi.py

    <Directory /var/www/xoviova>
        WSGIProcessGroup xoviova
        WSGIApplicationGroup %{GLOBAL}
        WSGIScriptReloading On
        Order deny,allow
        Allow from all
    </Directory>

    LogLevel warn
    ErrorLog /var/log/xoviova/error.log
    CustomLog /var/log/xoviova/access.log combined
</VirtualHost>
EOF

# ssl for apache
sudo cat <<EOF > /etc/apache2/sites-available/default-ssl
<IfModule mod_ssl.c>
<VirtualHost _default_:443>
    ServerName controller.xoviova.com

    Alias /img/ "/var/www/xoviova/webapp/static/img/"
    Alias /css/ "/var/www/xoviova/webapp/static/css/"
    Alias /js/ "/var/www/xoviova/webapp/static/js/"
    Alias /fonts/ "/var/www/xoviova/webapp/static/fonts/"

    <Directory /var/www/xoviova/webapp/static>
        Order deny,allow
        Allow from all
    </Directory>

    WSGIScriptAlias / /var/www/xoviova/wsgi.py

    <Directory /var/www/xoviova>
        WSGIProcessGroup xoviova
        WSGIApplicationGroup %{GLOBAL}
        WSGIScriptReloading On
        SSLOptions +StdEnvVars
        Order deny,allow
        Allow from all
    </Directory>

    LogLevel warn
    ErrorLog /var/log/xoviova/error.log
    CustomLog /var/log/xoviova/ssl_access.log combined

    SSLEngine on
    SSLCertificateFile    /etc/ssl/certs/ssl-cert-snakeoil.pem
    SSLCertificateKeyFile /etc/ssl/private/ssl-cert-snakeoil.key

    BrowserMatch "MSIE [2-6]" nokeepalive ssl-unclean-shutdown downgrade-1.0 force-response-1.0
    BrowserMatch "MSIE [17-9]" ssl-unclean-shutdown

</VirtualHost>
</IfModule>
EOF

# check out stackgeek-vm repo
sudo git clone https://github.com/StackMonkey/xovio-va.git /var/www/xoviova

# configure www directory
sudo chown -R www-data:www-data /var/www/
sudo chmod -R g+w www-data /var/www/

# enable ubuntu user to run web stuff
usermod -a -G www-data ubuntu

# install ssl
sudo a2enmod ssl
sudo a2ensite default-ssl

# restart apache
sudo service apache2 restart

# build the database and sync with pool operator
sudo su -c "/var/www/xoviova/manage.py reset" -s /bin/sh www-data
