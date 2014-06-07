#!/bin/bash
monit stop gunicorn
git pull
monit start gunicorn
chown -R ubuntu.ubuntu *