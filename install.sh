#!/bin/bash

# update repos
sudo apt-get update

# install git and pip
sudo apt-get install git
sudo apt-get install python-pip

# install flask bits via pip
sudo pip install Flask
sudo pip install flask-wtf
sudo pip install flask-appconfig
sudo pip install flask-bootstrap
