#!/bin/bash

# update repos
sudo apt-get update -y

# install git and pip
sudo apt-get install git -y
sudo apt-get install python-pip -y

# install flask bits via pip
sudo pip install Flask -y
sudo pip install flask-wtf -y
sudo pip install flask-appconfig -y
sudo pip install flask-bootstrap -y

# check out stackgeek-vm repo
sudo cd /root/
sudo git clone https://github.com/StackMonkey/stackmonkey-vm.git
