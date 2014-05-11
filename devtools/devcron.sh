#!/bin/bash

while [ 1 ] 
do
  echo "Running in 60"
  sleep 15
  echo "Running in 45"
  sleep 15
  echo "Running in 30"
  sleep 15
  echo "Running in 15"
  sleep 15
  ./manage.py instances
  ./manage.py trashman
done
