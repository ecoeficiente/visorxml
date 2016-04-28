run:
	DJANGO_SETTINGS_MODULE=visorxml.settings.development PATH=$(abspath ./node_modules/.bin):${PATH} venv/bin/python visorxml/manage.py runserver

collectstatic:
	grunt
	DJANGO_SETTINGS_MODULE=visorxml.settings.development venv/bin/python visorxml/manage.py collectstatic

updatepo:
	cd visorxml && ../venv/bin/django-admin makemessages -l es

install:
	python3 -m pyvenv venv
	venv/bin/python -m pip install -Ur requirements.txt
	mkdir visorxml/media/
	mkdir visorxml/served-static/
	npm install
	bower install
	grunt

installpackages:
	sudo aptitude install python3 python3-pip nodejs npm poppler-utils build-essential python3-dev libxml2-dev libxslt-dev libffi-dev zlig1g-dev  libjpeg-dev libopenjp-2-7-dev
	sudo npm install -g grunt-cli

