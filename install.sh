#!/bin/bash

# name: install.sh
# description: install script for utter.io appliance
# author: kordless@utter.io
# github: https://github.com/stackmonkey/utter-va

# update repos
sudo apt-get update -y

# time server
apt-get install ntp -y
service ntp restart

# install dependencies and services
sudo apt-get install git -y
sudo apt-get install sqlite3 -y
sudo apt-get install python-pip -y
sudo apt-get install build-essential -y
sudo apt-get install python-dev -y
sudo apt-get install unzip -y
sudo apt-get install monit -y

# IPy address util
sudo pip install IPy

# install and patch gevent
sudo apt-get install python-gevent -y
pip install gevent --upgrade

# install ngrok
sudo wget -qO /tmp/ngrok.zip https://dl.ngrok.com/linux_386/ngrok.zip
sudo unzip /tmp/ngrok.zip
sudo mv ngrok /usr/local/bin/ngrok

# install webserver
sudo pip install gunicorn

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
sudo pip install flask-socketio

# install openstack libraries for python
sudo pip install python-keystoneclient
sudo pip install python-glanceclient
sudo pip install python-cinderclient
sudo pip install python-novaclient

# check out the current release of utter-va
sudo mkdir /var/log/utterio/
sudo git clone https://github.com/StackMonkey/utter-va.git /var/www/utterio
git checkout tags/v0.7-beta.5

# configure www directory
sudo chown -R ubuntu:ubuntu /var/www/
sudo chmod -R g+w /var/www/

# set vim tabs
sudo cat <<EOF > /home/ubuntu/.vimrc
set tabstop=4
EOF
chown ubuntu.ubuntu /home/ubuntu/.vimrc

# configure monit
sudo cat <<EOF > /etc/monit/conf.d/ngrok
set httpd port 5150 and
    use address localhost
    allow localhost

set daemon 30
with start delay 5

check process ngrok matching "/usr/local/bin/ngrok -config /var/www/utterio/tunnel.conf start utterio"
    start program = "/var/www/utterio/tunnel.sh"
    stop program = "/usr/bin/killall screen"
EOF

sudo cat <<EOF > /etc/monit/conf.d/gunicorn
set httpd port 5150 and
    use address localhost
    allow localhost

set daemon 30
with start delay 5

check process gunicorn with pidfile /tmp/gunicorn.pid
    start program = "/var/www/utterio/gunicorn.sh"
    stop program = "/var/www/utterio/gunistop.sh"
EOF

sudo cat <<EOF > /etc/monit/conf.d/twitterbot
set httpd port 5150 and
    use address localhost
    allow localhost

set daemon 30
with start delay 5

check process twitterbot matching "manage.py tweetstream"
		start program = "/var/www/utterio/tweetstream.sh"
		stop program = "true"
EOF

# restart monit service
sudo service monit restart
sleep 2
sudo monit monitor all

# generate tokens and write into new config.py file
cp /var/www/utterio/config.py.template /var/www/utterio/config.py
SECRET_KEY=`date +%N | md5sum | cut -d' ' -f1`
sleep 1
CSRF_SESSION_KEY=`date +%N | md5sum | cut -d' ' -f1`
sed -e "
s,%SECRET_KEY%,$SECRET_KEY,g;
s,%CSRF_SESSION_KEY%,$CSRF_SESSION_KEY,g;
" -i /var/www/utterio/config.py

# change ownership of www directory
sudo chown -R ubuntu:ubuntu /var/www/
sudo chmod -R g+w /var/www/

# grab the IP address of the box
MYIP=$(/sbin/ifconfig eth0| sed -n 's/.*inet *addr:\([0-9\.]*\).*/\1/p')

# build the database and sync with pool operator
sudo su -c "/var/www/utterio/manage.py install -i $MYIP" -s /bin/sh ubuntu

# install crontab for ubuntu user to run every 15 minutes starting with a random minute
MICROS=`date +%N`
ONE=`expr $MICROS % 5`
TWO=`expr $ONE + 5`
THREE=`expr $ONE + 10`
FOUR=`expr $ONE + 15`
FIVE=`expr $ONE + 20`
SIX=`expr $ONE + 25`
SEVEN=`expr $ONE + 30`
EIGHT=`expr $ONE + 35`
NINE=`expr $ONE + 40`
TEN=`expr $ONE + 45`
ELEVEN=`expr $ONE + 50`
TWELVE=`expr $ONE + 55`

sudo cat <<EOF > /var/www/utterio/crontab
# run various manage commands every 15 minutes
$ONE,$FOUR,$SEVEN,$TEN * * * * /var/www/utterio/manage.py images > /dev/null 2>&1
$ONE,$FOUR,$SEVEN,$TEN * * * * /var/www/utterio/manage.py flavors > /dev/null 2>&1
$TWO,$FIVE,$EIGHT,$ELEVEN * * * * /var/www/utterio/manage.py salesman > /dev/null 2>&1
$THREE,$SIX,$NINE,$TWELVE * * * * /var/www/utterio/manage.py trashman > /dev/null 2>&1

# run various manage commands every 5 minutes
$ONE,$TWO,$THREE,$FOUR,$FIVE,$SIX,$SEVEN,$EIGHT,$NINE,$TEN,$ELEVEN,$TWELVE * * * * /var/www/utterio/manage.py housekeeper > /dev/null 2>&1

# run various manage commands every 1 minute
* * * * * /var/www/utterio/manage.py instances > /dev/null 2>&1
EOF
sudo crontab -u ubuntu /var/www/utterio/crontab

# finally, start downloading images
sudo su -c "/var/www/utterio/manage.py images" -s /bin/sh ubuntu