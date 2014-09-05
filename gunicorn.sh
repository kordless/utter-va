#!/bin/bash
cd /var/www/utterio/
/usr/local/bin/gunicorn -u ${1} -g ${2} -c /var/www/utterio/gunicorn.conf.py webapp:app
