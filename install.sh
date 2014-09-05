#!/bin/bash

# name: install.sh
# description: install script for utter.io appliance
# author: kordless@utter.io
# github: https://github.com/stackmonkey/utter-va


# define user/group name for services
export USER="stackmonkey"
export GROUP="stackmonkey"
export HOME="/var/www/${USER}"

# update repos
apt-get update -y

# time server
apt-get install ntp -y
service ntp restart

# install dependencies and services
apt-get install git -y
apt-get install sqlite3 -y
apt-get install python-pip -y
apt-get install build-essential -y
apt-get install python-dev -y
apt-get install unzip -y
apt-get install monit -y

# address libxslt compile errors when installing python-* openstack libs
apt-get install python-dev -y
apt-get install libxslt1-dev libxslt1.1 libxml2-dev libxml2 libssl-dev -y
apt-get install libffi-dev -y

# install ngrok
wget -qO /tmp/ngrok.zip https://dl.ngrok.com/linux_386/ngrok.zip
unzip /tmp/ngrok.zip
mv ngrok /usr/local/bin/ngrok

# need to create /var/www to put service user's home there
mkdir /var/www

# add user and group to run services as
groupadd ${GROUP}
useradd -g ${GROUP} -m -d ${HOME} ${USER}

# check out the current release of utter-va
mkdir /var/log/utterio/
chown ${USER}:${GROUP} /var/log/utterio/

# clone appliance code
sudo -u ${USER} git clone -b improve_installation https://github.com/StackMonkey/utter-va.git ${HOME}

# install all the python requirements
cd ${HOME}
sudo -u ${USER} pip install -U -r ./requirements.txt

# set vim tabs
cat <<EOF > /home/ubuntu/.vimrc
set tabstop=4
EOF
chown ubuntu.ubuntu /home/ubuntu/.vimrc

# configure monit
cat <<EOF > /etc/monit/conf.d/ngrok
set httpd port 5150 and
    use address localhost
    allow localhost

set daemon 30
with start delay 5

check process ngrok matching "/usr/local/bin/ngrok -config ${HOME}/tunnel.conf start utterio"
    start program = "${HOME}/tunnel.sh"
        as uid ${USER} and gid ${GROUP}
    stop program = "/usr/bin/killall screen"
EOF

cat <<EOF > /etc/monit/conf.d/gunicorn
set httpd port 5150 and
    use address localhost
    allow localhost

set daemon 30
with start delay 5

check process gunicorn with pidfile /tmp/gunicorn.pid
    start program = "${HOME}/gunicorn.sh"
        as uid ${USER} and gid ${GROUP}
    stop program = "${HOME}/gunistop.sh"
EOF

cat <<EOF > /etc/monit/conf.d/twitterbot
set httpd port 5150 and
    use address localhost
    allow localhost

set daemon 30
with start delay 5

check process twitterbot matching "manage.py tweetstream"
		start program = "${HOME}/tweetstream.sh"
        as uid ${USER} and gid ${GROUP}
		stop program = "/bin/true"
EOF

# restart monit service
service monit restart
sleep 2
monit monitor all

# generate tokens and write into new config.py file
sudo -u ${USER} cp ${HOME}/config.py.template ${HOME}/config.py
SECRET_KEY=`date +%N | md5sum | cut -d' ' -f1`
sleep 1
CSRF_SESSION_KEY=`date +%N | md5sum | cut -d' ' -f1`
sed -e "
s,%SECRET_KEY%,$SECRET_KEY,g;
s,%CSRF_SESSION_KEY%,$CSRF_SESSION_KEY,g;
" -i ${HOME}/config.py

# grab the IP address of the box
MYIP=$(/sbin/ifconfig eth0| sed -n 's/.*inet *addr:\([0-9\.]*\).*/\1/p')

# build the database and sync with pool operator
sudo -u ${USER} ${HOME}/manage.py install -i $MYIP

# install crontab for service user to run every 15 minutes starting with a random minute
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

cat <<EOF > ${HOME}/crontab
# run various manage commands every 15 minutes
$ONE,$FOUR,$SEVEN,$TEN * * * * ${HOME}/manage.py images > /dev/null 2>&1
$ONE,$FOUR,$SEVEN,$TEN * * * * ${HOME}/manage.py flavors > /dev/null 2>&1
$TWO,$FIVE,$EIGHT,$ELEVEN * * * * ${HOME}/manage.py salesman > /dev/null 2>&1
$TWO,$FIVE,$EIGHT,$ELEVEN * * * * ${HOME}/manage.py marketeer > /dev/null 2>&1
$THREE,$SIX,$NINE,$TWELVE * * * * ${HOME}/manage.py trashman > /dev/null 2>&1

# run various manage commands every 5 minutes
$ONE,$TWO,$THREE,$FOUR,$FIVE,$SIX,$SEVEN,$EIGHT,$NINE,$TEN,$ELEVEN,$TWELVE * * * * ${HOME}/manage.py housekeeper > /dev/null 2>&1

# run various manage commands every 1 minute whic break that into 15 second runs
* * * * * ${HOME}/manage.py instances -c 60 -f 15 > /dev/null 2>&1
* * * * * ${HOME}/manage.py falconer -c 60 -f 15 > /dev/null 2>&1
EOF
crontab -u ${USER} ${HOME}/crontab

# finally, start downloading images
sudo -u ${USER} ${HOME}/manage.py images
