#!/bin/bash
monit stop gunicorn
git pull
sleep 5
monit start gunicorn
chown -R /var/www/utterio/ubuntu.ubuntu *