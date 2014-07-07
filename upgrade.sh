#!/bin/bash
monit stop gunicorn
git pull
sleep 5
monit start gunicorn
chown ubuntu.ubuntu -R /var/www/utterio/