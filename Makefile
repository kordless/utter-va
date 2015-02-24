# makefile

serve:
	./manage.py serve

cron:
	cd ./devtools; ./devcron.sh	
