#!/bin/bash

# name: install.sh
# description: install script for xovio controller vm
# author: info@xovio.com 
# github: https://github.com/StackMonkey/xovio-va

# pool operator domian
POOL_URL="stackmonkey.com"
POOL_SHORT_NAME="stackmonkey"

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
mkdir /var/log/$POOL_SHORT_NAME/
chown -R www-data:www-data /var/log/$POOL_SHORT_NAME/
sudo cat <<EOF > /etc/apache2/sites-available/default
<VirtualHost *:80>
    ServerName controller.$POOL_URL

    Alias /img/ "/var/www/$POOL_SHORT_NAME/webapp/static/img/"
    Alias /css/ "/var/www/$POOL_SHORT_NAME/webapp/static/css/"
    Alias /js/ "/var/www/$POOL_SHORT_NAME/webapp/static/js/"
    Alias /fonts/ "/var/www/$POOL_SHORT_NAME/webapp/static/fonts/"

    <Directory /var/www/$POOL_SHORT_NAME/webapp/static>
        Order deny,allow
        Allow from all
    </Directory>

    WSGIDaemonProcess $POOL_SHORT_NAME user=www-data group=www-data threads=5
    WSGIScriptAlias / /var/www/$POOL_SHORT_NAME/wsgi.py

    <Directory /var/www/$POOL_SHORT_NAME>
        WSGIProcessGroup $POOL_SHORT_NAME
        WSGIApplicationGroup %{GLOBAL}
        WSGIScriptReloading On
        Order deny,allow
        Allow from all
    </Directory>

    LogLevel warn
    ErrorLog /var/log/$POOL_SHORT_NAME/error.log
    CustomLog /var/log/$POOL_SHORT_NAME/access.log combined
</VirtualHost>
EOF

# ssl for apache
sudo cat <<EOF > /etc/apache2/sites-available/default-ssl
<IfModule mod_ssl.c>
<VirtualHost _default_:443>
    ServerName controller.$POOL_SHORT_NAME.com

    Alias /img/ "/var/www/$POOL_SHORT_NAME/webapp/static/img/"
    Alias /css/ "/var/www/$POOL_SHORT_NAME/webapp/static/css/"
    Alias /js/ "/var/www/$POOL_SHORT_NAME/webapp/static/js/"
    Alias /fonts/ "/var/www/$POOL_SHORT_NAME/webapp/static/fonts/"

    <Directory /var/www/$POOL_SHORT_NAME/webapp/static>
        Order deny,allow
        Allow from all
    </Directory>

    WSGIScriptAlias / /var/www/$POOL_SHORT_NAME/wsgi.py

    <Directory /var/www/$POOL_SHORT_NAME>
        WSGIProcessGroup $POOL_SHORT_NAME
        WSGIApplicationGroup %{GLOBAL}
        WSGIScriptReloading On
        SSLOptions +StdEnvVars
        Order deny,allow
        Allow from all
    </Directory>

    LogLevel warn
    ErrorLog /var/log/$POOL_SHORT_NAME/error.log
    CustomLog ${APACHE_LOG_DIR}/ssl_access.log combined

    SSLEngine on
    SSLCertificateFile    /etc/ssl/certs/ssl-cert-snakeoil.pem
    SSLCertificateKeyFile /etc/ssl/private/ssl-cert-snakeoil.key

    BrowserMatch "MSIE [2-6]" \
        nokeepalive ssl-unclean-shutdown \
        downgrade-1.0 force-response-1.0
    BrowserMatch "MSIE [17-9]" ssl-unclean-shutdown

</VirtualHost>
</IfModule>
EOF

# check out stackgeek-vm repo
sudo su
cd /var/www/
sudo git clone https://github.com/StackMonkey/xovio-va.git $POOL_SHORT_NAME

# build the database and sync with pool operator
su www-data
cd /var/www/$POOL_SHORT_NAME/
/var/www/$POOL_SHORT_NAME/manage.py reset

# configure www directory
sudo chown -R www-data:www-data /var/www/

# install ssl
sudo a2enmod ssl
a2ensite default-ssl

# restart apache
sudo service apache2 restart
