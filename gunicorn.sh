#!/bin/bash
cd /var/www/utterio/
/usr/local/bin/gunicorn -c /var/www/utterio/gunicorn.conf.py webapp:app
