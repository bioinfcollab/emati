This document describes how to deploy this project to a live production environment.


# Project Setup
Clone the project from https://projects.biotec.tu-dresden.de/redmine/projects/emati-de/.

Install all dependencies listed in the `requirements.txt` which is located at the project root directory:
```
pip install -r requirements.txt
```

Make sure you are using Python 3. Python 2 is no longer supported in current versions of Django. See [here](https://docs.djangoproject.com/en/2.1/faq/install/#faq-python-version-support) for an overview of supported Python versions.


# Django settings
Go to `emati/emati/settings/` and copy and rename the `*.py.example` files to simply `*.py`. Fill the settings files with your real values and secret keys. See [here](https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/) for variables important for deployment or [here](https://docs.djangoproject.com/en/2.1/ref/settings/) for a list of all available settings.

Specify which settings-file to use (production or development) by declaring the environment variable `DJANGO_SETTINGS_MODULE`
```
export DJANGO_SETTINGS_MODULE=emati.settings.production
```
Note that by default the production settings will be used.


# Apache and mod_wsgi
A complete guide on how to deploy a Django project using Apache and mod_wsgi can be found [here](https://docs.djangoproject.com/en/2.1/howto/deployment/). `mod_wsgi` is an Apache module which can host any Python WSGI application, including Django. You can get it from [here](https://modwsgi.readthedocs.io/en/develop/#). Follow the installation instructions outlined in the documentation.

After successfully setting up Apache with mod_wsgi, the application file you want to point to is located at `/your/path/to/the/project/emati/wsgi.py`.


# Database
Create a new MySQL database and a new user that django will use to access that database (you can call them whatever you want, e.g. `emati` and `emati-user`). Remember to add this connection to your settings file.

The django-user must have access to creating new tables. This is necessary so that Django can create or modify the tables automatically. To setup your database, run the following command from the project's root directory:
```
python manage.py migrate
```
This will create all required tables automatically.

Now create an admin user for the website. This user will have all rights and will be able to manage the website via the built-in admin views.
```
python manage.py createsuperuser
```


# Elasticsearch
Download Elasticsearch from [here](https://www.elastic.co/downloads/elasticsearch). 
Follow the [instructions](https://www.elastic.co/guide/en/elasticsearch/guide/current/deploy.html) for deployment.

Note that Elasticsearch is a separate web service. You can host it on a completely different machine. The communication between Django and Elasticsearch is configured in the Django settings.

Open your emati production settings file and configure the `WEBSITE_SEARCH_CLIENT` variable. It should create a valid connection to your Elasticsearch server. See [here](https://elasticsearch-py.readthedocs.io/en/master/#ssl-and-authentication) for some notes on authentication and SSL.


# Additional database configuration
Once the project is up and running you must configure your social logins. This is easily done via Django's web-interface. Open a browser and navigate to wherever the project is now hosted, followed by `/admin`. Login with your superuser credentials. You should now see the Django administration page.

At `Sites` add/edit the site to your personal "Domain name" and "Display name". For example set the domain name to "emati.de" and display name to "Emati".

At `Social Applications` add a new provider for Google and one for Facebook. For this, pick the provider from the dropdown list, give it an arbitrary name ("google"/"facebook"), add your Client IDs and Secret Keys, and move the site which you configured in the previous step from "Available sites" to "Chosen sites".


# Initial data fetching
Before making the website available to the public you should download some initial articles. You can download all papers published after a specific date using the command
```
python manage.py fetch_papers -s YYYY-MM-DD
```
The command will break down the time span into batches of one week, to ease the load on our sources. Once that is done, don't forget to update your search index:
```
python manage.py update_search_index
```


# Weekly content generation
Some commands have to be run regularly to keep generating content (e.g. using Cron). Make sure the following commands are run in this order every sunday night:
```
python manage.py fetch_papers --last-week
python manage.py update_search_index --last-week
python manage.py update_classifiers
python manage.py create_recommendations --last-week
python manage.py create_statistics
python manage.py send_newsletter
```

These commands should be run from the project's root directory. Make sure to run them as the same user that is running the server. Else new log files could be created that are owned by a different user and the server won't be able to write to them.