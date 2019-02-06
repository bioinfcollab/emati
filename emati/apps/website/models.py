import os
import json
from sklearn.externals import joblib

from django.db import models
from django.db.utils import IntegrityError
from django.db.models.signals import pre_delete
from django.utils import timezone
from django.conf import settings
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from annoying.fields import AutoOneToOneField


import logging
logger = logging.getLogger(__name__)


class UserProfile(models.Model):
    user = AutoOneToOneField(
        settings.AUTH_USER_MODEL,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    newsletter = models.BooleanField(default=True)
    terms_consent = models.BooleanField(default=False)
    recent_interactions = models.IntegerField(
        default=0,
        verbose_name="number of interactions since last classifier retraining"
    )
    last_visit = models.DateTimeField(default=timezone.now)



def user_directory_path(instance, filename):
    """Specifies the path for a user upload."""
    # file will be uploaded to MEDIA_ROOT/uploads/user_<id>/<filename>
    return 'uploads/user_{0}/{1}'.format(instance.user.id, filename)

class UserUpload(models.Model):
    file = models.FileField(upload_to=user_directory_path)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='uploads')



class UserLogManager(models.Manager):
    def create_log(self, user, event, context={}, **kwargs):
        """Creates a new log for the specified user and event. 
        
        Context can either be supplied directly as a dictionary or specified
        implicitly via additional keyword arguments. These will overwrite any
        keys with the same name in the supplied dictionary.

        Example:
        create_log(user=u, event=e, context={'article_id':1234})
        create_log(user=u, event=e, article_id=1234)
        """
        new_log = self.create(user=user, event=event)
        for key, value in kwargs.items():
            context[key] = value
        new_log.set_context_dict(context)
        new_log.save()
        return new_log


class UserLog(models.Model):
    """An event log for a user's action.

    Supports a fixed set of events. Further details for each event are stored
    in a context dictionary. WARNING: if you need to change this dict, then
    only overwrite it with a new one. Do not assign values to a specific key,
    as this will not change the underlying JSON representation. 
    E.g. Don't do this:
        my_log.context_dict['article_id'] = 1234 
    Instead do this:
        my_log.context_dict = {'article_id': 1234}

    To create a new log use the `create_log` method:
        UserLog.objects.create_log(user=u, event=e, context={...})
    """

    class Events():
        CLICK = 'CLICK'
        LIKE = 'LIKE'
        DISLIKE = 'DISLIKE'
        SEARCH = 'SEARCH'
        REGISTRATION = 'REGISTRATION'
    
    EVENT_CHOICES = [
        (Events.CLICK, 'Click'),
        (Events.LIKE, 'Like'),
        (Events.DISLIKE, 'Dislike'),
        (Events.SEARCH, 'Search'),
        (Events.REGISTRATION, 'Registration'),
    ]

    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.CharField(max_length=50, choices=EVENT_CHOICES, blank=False)
    context_json_string = models.TextField(blank=False)

    objects = UserLogManager()

    def get_context_dict(self):
        return json.loads(self.context_json_string)

    def set_context_dict(self, d):
        self.context_json_string = json.dumps(d)

    def __str__(self):
        return "user:{}, event:{}, context:{}".format(
            self.user.pk, self.event, self.context_json_string
        )



class Article(models.Model):

    # Do not allow duplicate titles
    title = models.CharField(max_length=255, unique=True)
    abstract = models.TextField()
    journal = models.CharField(max_length=255)
    authors_string = models.TextField()
    pubdate = models.DateField(db_index=True)
    url_fulltext = models.URLField()
    url_source = models.URLField()

    def save(self, *args, **kwargs):
        # We want to enforce unique titles. Therefore the DB must index over
        # the title field. MySQL can't index fields that are longer than 255
        # characters. Hence we must ensure that article titles are less than
        # 255 characters.

        # Cut off long titles and add some dots instead. 
        if len(self.title) > 255:
            self.title = self.title[:251] + ' ...'
            
        super(Article, self).save(*args, **kwargs)

    @property
    def authors_list(self):
        return self.authors_string.split(';')

    @authors_list.setter
    def authors_list(self, authors_list):
        self.authors_string = ';'.join(authors_list)


class Recommendation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    score = models.FloatField(default=0, db_index=True) # index for faster ordering
    clicked = models.BooleanField(default=False)
    liked = models.BooleanField(default=False)
    disliked = models.BooleanField(default=False)

    class Meta:
        # Order descending by score
        ordering = ["-score"]

    def validate_unique(self, exclude=None):
        # Get all recommendations with the same user and article
        qs = Recommendation.objects.filter(user=self.user, article=self.article)
        if self.pk is None:
            if qs.exists():
                raise IntegrityError("Item already exists")

    def save(self, *args, **kwargs):
        # ALWAYS before saving ensure we avoid duplicates. Because by default
        # validate_unique is only called when submitting forms.
        self.validate_unique()
        super(Recommendation, self).save(*args, **kwargs)



class Classifier(models.Model):
    """A machine learning model used for predicting scores.

    Consists of a vectorizer and a classifier. The database only stores the
    respective filenames and the associated user.
    """
    user = AutoOneToOneField(
        settings.AUTH_USER_MODEL,
        primary_key=True,
        on_delete=models.CASCADE, 
        related_name='classifier',
    )
    path_clf = models.CharField(max_length=255)
    path_vec = models.CharField(max_length=255)
    classifier = None
    vectorizer = None

    def is_initialized(self):
        if not self.classifier:
            return False
        if not self.vectorizer:
            return False
        return True

    def __init__(self, *args, **kwargs):
        super(Classifier, self).__init__(*args, **kwargs)
        self.classifier = self._load_from_file(self.path_clf)
        self.vectorizer = self._load_from_file(self.path_vec)

    def _load_from_file(self, path):
        """Loads a file from disk. Returns None if no file was found."""
        if not path:
            return None
        try:
            return joblib.load(path)
        except FileNotFoundError as e:
            # Apparently no classifier exists that we could load
            return None

    def get_path(self, filename):
        """Returns the absolute path for a given file when it belongs 
        to this classifier."""
        return os.path.join(
            settings.BASE_DIR,
            settings.MEDIA_ROOT,
            'classifiers/user_{}/{}'.format(self.user.pk, filename)
        )

    def create_path(self, path):
        """Creates necessary directories in a path if they don't exist."""
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))

    def save(self, *args, **kwargs):
        if self.classifier:
            self.path_clf = self.get_path('classifier.joblib')
            self.create_path(self.path_clf)
            joblib.dump(self.classifier, self.path_clf)
        if self.vectorizer:
            self.path_vec = self.get_path('vectorizer.joblib')
            self.create_path(self.path_vec)
            joblib.dump(self.vectorizer, self.path_vec)
        super(Classifier, self).save(*args, **kwargs)

    def delete_files(self):
        logger.info("Deleting classifier files (user {}) ...".format(self.user.pk))
        try:
            os.remove(self.path_clf)
            os.remove(self.path_vec)
        except FileNotFoundError as e:
            logger.error(e)

        dir_clf = os.path.dirname(self.path_clf)
        dir_vec = os.path.dirname(self.path_vec)
        try:
            os.rmdir(dir_clf)
            if dir_clf != dir_vec:
                os.rmdir(dir_vec)
        except OSError as e:
            logger.error(e)


@receiver(pre_delete, sender=Classifier)
def classifier_pre_delete(sender, instance, *args, **kwargs):
    # NOTE: Using signals is better than overriding the `delete()` method.
    # `delete()` is only called when explicitly deleting an instance; not when
    # it's deleted as part of a cascade delete (`user.delete()`). This signal
    # however is called in both cases.
    instance.delete_files()