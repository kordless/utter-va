#!/bin/bash
cd /var/www/xoviova/
/usr/local/bin/gunicorn -c /var/www/xoviova/gunicorn.conf.py webapp:app
