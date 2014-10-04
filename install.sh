#!/bin/bash

# name: install.sh
# description: install script for utter.io appliance
# author: kordless@utter.io
# github: https://github.com/stackmonkey/utter-va


# define user/group name for services
export USER="stackmonkey"
export GROUP="stackmonkey"
export BASE_DIR="/var/www/utterio"

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

# create a 10G datastore for the image cache
apt-get install btrfs-tools -y
IMG_CACHE_FILE="/var/image_cache.img"
IMG_CACHE_MNT_PNT="/mnt/image_cache"
dd if=/dev/zero of=${IMG_CACHE_FILE} bs=1024 count=10485760
losetup -f ${IMG_CACHE_FILE}
LOOP_DEV=$(losetup -a | grep "${IMG_CACHE_FILE}" | awk -F ':' '{print $1}')
mkfs.btrfs -L image_cache ${LOOP_DEV}
mkdir ${IMG_CACHE_MNT_PNT}
echo "${IMG_CACHE_FILE}	${IMG_CACHE_MNT_PNT}	btrfs	user,loop,auto,nodev,noexec	0 0" >> /etc/fstab
mount ${IMG_CACHE_MNT_PNT}

# install nginx caching reverse proxy
apt-get install nginx -y
cat <<EOF > /etc/nginx/sites-available/reverse_proxy.conf
proxy_cache_path /mnt/image_cache levels=1:2 keys_zone=IMGCACHE:10m inactive=14d;
server {
	listen 8080;

	location ~* "^/([a-zA-Z0-9\.\-]+)/(.*)$" {
		set \$real_host \$1;
		set \$real_uri \$2;
		resolver 8.8.8.8;
		proxy_pass             http://\$real_host/\$real_uri;
		proxy_set_header       Host \$real_host;
		proxy_cache            IMGCACHE;
		proxy_cache_valid      200  1d;
		proxy_cache_use_stale  error timeout invalid_header updating http_500 http_502 http_503 http_504;
	}
}
EOF
ln -s /etc/nginx/sites-available/reverse_proxy.conf /etc/nginx/sites-enabled/reverse_proxy.conf
nginx -s reload

# add user and group to run services as
groupadd ${GROUP}
useradd -g ${GROUP} -m -d /var/lib/stackmonkey ${USER}

# create log directory
mkdir /var/log/utterio/
chown ${USER}:${GROUP} /var/log/utterio/

# need to create /var/www to put service data in
mkdir /var/www

# clone appliance code
git clone https://github.com/StackMonkey/utter-va.git ${BASE_DIR}

# chown it all to the service user
chown -R ${USER}:${GROUP} ${BASE_DIR}

# install all the python requirements
pip install -U -r ${BASE_DIR}/requirements.txt

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

check process ngrok matching "/usr/local/bin/ngrok -config ${BASE_DIR}/tunnel.conf start utterio"
    start program = "${BASE_DIR}/tunnel.sh"
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
    start program = "${BASE_DIR}/gunicorn.sh ${USER} ${GROUP}"
    stop program = "${BASE_DIR}/gunistop.sh"
EOF

cat <<EOF > /etc/monit/conf.d/twitterbot
set httpd port 5150 and
    use address localhost
    allow localhost

set daemon 30
with start delay 5

check process twitterbot matching "manage.py tweetstream"
		start program = "${BASE_DIR}/tweetstream.sh"
        as uid ${USER} and gid ${GROUP}
		stop program = "/bin/true"
EOF

# restart monit service
service monit restart
sleep 2
monit monitor all

# generate tokens and write into new config.py file
sudo -u ${USER} cp ${BASE_DIR}/config.py.template ${BASE_DIR}/config.py
SECRET_KEY=`date +%N | md5sum | cut -d' ' -f1`
sleep 1
CSRF_SESSION_KEY=`date +%N | md5sum | cut -d' ' -f1`
sed -e "
s,%SECRET_KEY%,$SECRET_KEY,g;
s,%CSRF_SESSION_KEY%,$CSRF_SESSION_KEY,g;
" -i ${BASE_DIR}/config.py

# grab the IP address of the box
MYIP=$(/sbin/ifconfig eth0| sed -n 's/.*inet *addr:\([0-9\.]*\).*/\1/p')

# build the database and sync with pool operator
sudo -u ${USER} ${BASE_DIR}/manage.py install -i $MYIP

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

cat <<EOF > ${BASE_DIR}/crontab
# run various manage commands every 15 minutes
$ONE,$FOUR,$SEVEN,$TEN * * * * ${BASE_DIR}/manage.py images > /dev/null 2>&1
$ONE,$FOUR,$SEVEN,$TEN * * * * ${BASE_DIR}/manage.py flavors > /dev/null 2>&1
$TWO,$FIVE,$EIGHT,$ELEVEN * * * * ${BASE_DIR}/manage.py salesman > /dev/null 2>&1
$TWO,$FIVE,$EIGHT,$ELEVEN * * * * ${BASE_DIR}/manage.py marketeer > /dev/null 2>&1
$THREE,$SIX,$NINE,$TWELVE * * * * ${BASE_DIR}/manage.py trashman > /dev/null 2>&1

# run various manage commands every 5 minutes
$ONE,$TWO,$THREE,$FOUR,$FIVE,$SIX,$SEVEN,$EIGHT,$NINE,$TEN,$ELEVEN,$TWELVE * * * * ${BASE_DIR}/manage.py housekeeper > /dev/null 2>&1

# run various manage commands every 1 minute whic break that into 15 second runs
* * * * * ${BASE_DIR}/manage.py instances -c 60 -f 15 > /dev/null 2>&1
* * * * * ${BASE_DIR}/manage.py falconer -c 60 -f 15 > /dev/null 2>&1
EOF
crontab -u ${USER} ${BASE_DIR}/crontab

# finally, start downloading images
sudo -u ${USER} ${BASE_DIR}/manage.py images
