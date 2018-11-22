Some instructions on how to set this project up for local development.


# Project setup
Install virtualenv and virtualenvwrapper
(https://virtualenvwrapper.readthedocs.io/en/latest/)
```
sudo pip install virtualenv
sudo pip install virtualenvwrapper
```

Create a new virtual environment for the project. Current versions of Django only support Python 3. (To find your python3 binary use `which python3`.)
```
mkvirtualenv --python=/usr/bin/python3 emati
```
This will create a new virtual environment at `~/.virtualenvs/emati/`. You can leave the current virtualenv anytime with `deactivate` or start working on it again with `workon emati`.

Clone the project to a directory of your choice using Git. Go into the project's root directory, activate the virtual environment and install all the project's dependencies into your virtualenv:
```
workon emati
pip install -r requirements.txt
```


# Project settings
Go to `emati/settings/` and copy and rename the `*.py.example` files to simply `*.py`. Fill in your real values and secrets. For development you don't have to worry about the project's `SECRET_KEY`. The only settings you need to change can be found in `development.py`. The development settings import all the production settings and simply overwrite those that are needed to get the project running locally. One variable you must absolutely set, however, is the database connection. See the next section for more info on that.

Once your settings are configured you must tell Django which one to use. You can do this either by setting the environment variable `DJANGO_SETTINGS_MODULE`
```
export DJANGO_SETTINGS_MODULE=emati.settings.development
```
Or you can specify it explicitly every time you start the server:
```
python manage.py runserver --settings=emati.settings.development
```
Note that by default the production settings will be used.


# Database
You need to connect your project to a local database. Your first option is to use SQLite, which is very lightweight and easy to setup. You just need to set the `DATABASES` variable in your settings file and you are done with this step. Django will create the database file automatically. The second option is to use something like MySQL. In this case you have to set up a new database and a user that Django will use to access that database. It's important that this user has complete rights over this database, so that Django can automatically create and modify the tables. Here are some example SQL commands:
```
CREATE DATABASE emati CHARACTER SET utf8;
GRANT ALL PRIVILEGES ON emati.* TO 'django-emati'@'localhost' IDENTIFIED BY 'yourpassword';
```
This creates the user `django-emati` that has the password `yourpassword` and has all rights for the database `emati` which is hosted on `localhost`. 

Once your database is set up and the connection is configured in the settings, you can let Django create the required tables:
```
python manage.py migrate
```


# Create an admin account
Once the project is connected to a database you can create users. Create a new superuser with
```
python manage.py createsuperuser
```
Follow the instructions and give the user a name, email and password. This will be your admin account that you will use later to manage the project via Django's built-in administration views.


# Starting the server
From your project's root directory run
```
python manage.py runserver
```
Open a browser and navigate to `localhost:8000`. You should see your local copy of the project up and running. Now go to `localhost:8000/admin` and log in with your superuser credentials. Here you can see some more settings that can be configured.


# (Optional) setting up social login
This isn't required for local development, but if you want to enable the login via Facebook or Google, there are some more steps you have to take. Go to `localhost:8000/admin` and click on "Social Applications". There you can add a new provider for each social login. One for Facebook and one for Google. You can create some dummy projects with Google and Facebook via their Developer Consoles. Once you have the necessary credentials (id and secret) you can insert them on the Django admin page. And don't forget to add your "Site" from "Available sites" to "Chosen sites".

Google Developer console: 
console.development.google.com

Facebook developer console:
developers.facebook.com

When creating the OAuth app on the site of the provider set the callback URL to
```
http://localhost:8000/accounts/google/login/callback
http://localhost:8000/accounts/facebook/login/callback
http://localhost:8000/accounts/<YOUR_PROVIDER>/login/callback
```

More info can be found here:
https://django-allauth.readthedocs.io/en/latest/providers.html


# Elasticsearch
The project's search feature relies on Elasticsearch.
Download Elasticsearch from here https://www.elastic.co/downloads/elasticsearch
The simplest option is to download the .tar and then unpack it:
```
$ curl -L -O https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-6.3.2.tar.gz
$ tar -xvf elasticsearch-6.3.2.tar.gz
$ cd elasticsearch-6.3.2
$ bin/elasticsearch
```
Running `bin/elasticsearch` starts your elasticsearch server on port 9200. To check if its working open a browser and navigate to `localhost:9200`. You should see some kind of response.


# Creating content
At this point everything is up and running. Let's create some content to display on our website.
```
python manage.py fetch_papers --last-week
python manage.py update_search_index --last-week
```
This loads the papers from last week into the database and enables you to search for them. You can download any timespan using `fetch_papers -s 2000-01-02 -e 2000-03-04`. Then open a browser and navigate to `localhost:8000`. Log in or create a new account (verification mails should be printed to the console). Upload a reference file (under "Settings") or search for some papers and click or like or dislike them. This creates training data. Now run
```
python manage.py train_classifiers
python manage.py create_recommendations --last-week
```
This creates a classifier for your account and creates some recommendations for last week's papers. Usually these commands are run weekly to create new content. You can read more about this in the deployment instructions.
