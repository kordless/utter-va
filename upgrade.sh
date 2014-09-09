#!/bin/bash

USER=$(stat --printf="%U" /var/www/utterio/utterio.db)
GROUP=$(stat --printf="%G" /var/www/utterio/utterio.db)

echo "Switching to master branch."
git checkout master
git pull
sleep 3
chown ${USER}:${GROUP} -R /var/www/utterio/
monit restart gunicorn
