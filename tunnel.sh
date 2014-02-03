#!/bin/bash

# called by monit to monitor ngrok

# only try to start ngrok if we have a tunnel.conf file
if [ -f /var/www/xoviova/tunnel.conf ] then
    /usr/bin/screen -d -m /usr/local/bin/ngrok -config /var/www/xoviova/tunnel.conf start xoviova
fi