#!/bin/bash

# grab ngrok token and enpoint hostname
NGROK_TOKEN=$1
SERVICE_ENDPOINT_HOSTAME=$2
API_TOKEN=$3

# configure ngrok
sudo cat <<EOF > /root/.ngrok
auth_token: $NGROK_TOKEN
tunnels:
  $SERVICE_ENDPOINT_HOSTAME:
    proto:
      https: "80"
    auth: xovio:$API_TOKEN
EOF

# configure monit
sudo cat <<EOF > /etc/monit/conf.d/xovio
set daemon 120
with start delay 30
check process ngrok matching "/usr/local/bin/ngrok start $SERVICE_ENDPOINT_HOSTAME"
start program = "/usr/bin/screen -d -m /usr/local/bin/ngrok start $SERVICE_ENDPOINT_HOSTAME"
stop program = "/usr/bin/killall ngrok"
EOF
