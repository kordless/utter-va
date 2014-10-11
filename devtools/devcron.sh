#!/bin/bash
cd ..
while [ 1 ] 
do
  echo "Running...flavors"
  ./manage.py flavors
  
  echo "Running...images"
  ./manage.py images

  echo "Running...instances"
  ./manage.py instances

  echo "Running...housekeeper"
  ./manage.py housekeeper

  echo "Running...trashman"
  ./manage.py trashman

  echo "Running...salesman"
  ./manage.py salesman

  echo "Running...falconer"
  ./manage.py falconer

  echo "Running...marketeer"
  ./manage.py marketeer
  echo "Running in 1"
  sleep 1
  git pull
done
