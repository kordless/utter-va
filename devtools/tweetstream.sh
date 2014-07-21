#!/bin/bash
cd ../

while [ 1 ]
do
  ./manage.py tweetstream
  echo "sleeping 5 seconds before restarting..."
	sleep 5
done
