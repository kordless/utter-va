#!/bin/bash
echo "Switching to master branch."
git checkout master
git pull
sleep 3
chown ubuntu.ubuntu -R /var/www/utterio/
monit restart gunicorn