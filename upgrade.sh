#!/bin/bash
git pull
sleep 3
chown ubuntu.ubuntu -R /var/www/utterio/
monit restart gunicorn