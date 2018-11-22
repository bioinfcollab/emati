Emati is a recommender system for biomedical literature.
The project is built on Django. It uses django-allauth for user management and Elasticsearch to provide a search for papers.


# Project Structure
The project is divided into the following apps:
* website: The main app.
* machinelearning: A custom python module that handles everything related to training and using machine learning classifiers.
* fetching: A custom python module that handles everything related to getting articles from various sources and storing them in our database.
* dashboard: A separate website that displays statistics about the project.

```
+ emati
  + docs      (documentation)
  + emati     (main project)
    + apps
      + dashboard        (Django app)
      + fetching         (custom python module)
      + machinelearning  (custom python module)
      + website          (Django app)
    + settings
  + media       (user uploads, classifiers, ...)
  + static      (js, css, images)
  + templates   (html templates)
  + tests       (unit tests)
```


# Tests
To run the tests against the current environment:
```
python manage.py test
```
