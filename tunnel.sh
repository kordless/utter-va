#!/bin/bash

# called by monit to monitor ngrok - only used when running in production
# if you want to start the tunnel for dev, do the following: 
# ngrok -config=tunnel.conf start utterio

# only try to start ngrok if we have a tunnel.conf file
if [ -f /var/www/utterio/tunnel.conf ]; then
    /usr/bin/screen -d -m /usr/local/bin/ngrok -config /var/www/utterio/tunnel.conf start utterio
fi
