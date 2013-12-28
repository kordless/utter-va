#!/bin/bash

# update repos
sudo apt-get update -y

# install git and pip
sudo apt-get install git -y
sudo apt-get install python-pip -y

# install flask bits via pip
sudo pip install Flask
sudo pip install flask-wtf
sudo pip install flask-appconfig
sudo pip install flask-bootstrap

# check out stackgeek-vm repo
sudo su
cd /root/
sudo git clone https://github.com/StackMonkey/stackmonkey-vm.git
