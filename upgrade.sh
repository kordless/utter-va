#!/bin/bash
monit stop gunicorn
git pull
monit start gunicorn
chown -R /var/www/utterio/ubuntu.ubuntu *