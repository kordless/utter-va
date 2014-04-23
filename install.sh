#!/bin/bash

# name: install.sh
# description: install script for xovio controller vm
# author: info@xovio.com 
# github: https://github.com/StackMonkey/xovio-va

# overwrite the existing index.html file

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
sudo pip install --upgrade pyopenssl

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
sudo pip install flask-seasurf

# install openstack libraries for python
sudo pip install python-keystoneclient
sudo pip install python-glanceclient
sudo pip install python-cinderclient
sudo pip install python-novaclient

# configure apache
sudo mkdir /var/log/xoviova/
sudo chown -R www-data:www-data /var/log/xoviova/
sudo cat <<EOF > /etc/apache2/sites-available/default
WSGIDaemonProcess xoviova user=www-data group=www-data threads=5
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
sudo chmod -R g+w /var/www/

# enable ubuntu user to run web stuff
usermod -a -G www-data ubuntu

# install ssl
sudo a2enmod ssl
sudo a2ensite default-ssl

# restart apache
sudo service apache2 restart

# configure monit
sudo cat <<EOF > /etc/monit/conf.d/xoviova
set httpd port 5150 and
    use address localhost
    allow localhost

set daemon 120
with start delay 10
check process ngrok matching "/usr/local/bin/ngrok -config /var/www/xoviova/tunnel.conf start xoviova"
    start program = "/var/www/xoviova/tunnel.sh"
    stop program = "/usr/bin/killall screen"
EOF

# restart monit service
sudo service monit restart
sleep 2
sudo monit monitor all

# grab the IP address of the box
MYIP=$(/sbin/ifconfig eth0| sed -n 's/.*inet *addr:\([0-9\.]*\).*/\1/p')

# build the database and sync with pool operator
sudo su -c "/var/www/xoviova/manage.py install $MYIP" -s /bin/sh www-data

# install crontab for www-data to run every 15 minutes
MICROS=`date +%N`
FIRST=`expr $MICROS % 15`
SECOND=`expr $FIRST + 15`
THIRD=`expr $FIRST + 30`
FOURTH=`expr $FIRST + 45`

sudo cat <<EOF > /var/www/xoviova/crontab
# run various syncs every 15 minutes with servers
$FIRST,$SECOND,$THIRD,$FOURTH * * * * /var/www/xoviova/manage.py images > /dev/null 2>&1
$FIRST,$SECOND,$THIRD,$FOURTH * * * * /var/www/xoviova/manage.py flavors > /dev/null 2>&1
$FIRST,$SECOND,$THIRD,$FOURTH * * * * /var/www/xoviova/manage.py addresses > /dev/null 2>&1
$FIRST,$SECOND,$THIRD,$FOURTH * * * * /var/www/xoviova/manage.py instances > /dev/null 2>&1
EOF
sudo crontab -u www-data /var/www/xoviova/crontab

# finally, start downloading images
sudo su -c "/var/www/xoviova/manage.py images" -s /bin/sh www-data
