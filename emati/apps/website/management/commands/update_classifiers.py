import datetime

from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.conf import settings
from django.db.models import Q
from django.contrib.auth.models import User

from website.models import Recommendation

import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Retrains a classifier if enough new data samples are available.'


    # Amount of new interactions required to trigger a retraining. Use a
    # combination of percentage and absolute interactions. Whatever case
    # occurs first triggers the retraining.
    #
    # Percentage in relation to total interactions so far. Example: a user
    # has clicked/liked/disliked 100 articles in total. A threshold of 0.1
    # means that 100*0.1 = 10 new interactions since the last training are
    # needed to train the classifier anew.
    RETRAINING_THRESHOLD_PERCENT = 0.1
    # Absolute number of new interactions required to trigger a retraining.
    RETRAINING_THRESHOLD_ABSOLUTE = 10


    def add_arguments(self, parser):
        parser.add_argument('user_ids', type=int, nargs='*', help="")


    def _get_user_list(self, **options):
        """Returns the list of users we are supposed to work on."""
        if options['user_ids']:
            return User.objects.filter(pk__in=options['user_ids'])
        else:
            return User.objects.all()


    def handle(self, *args, **options):
        """The main entrypoint for this command."""
        
        users = self._get_user_list(**options)
        if not users:
            logger.warning("No users to work with.")
            return
        
        for u in users:
            if self._retraining_permitted(u):
                logger.info(
                    "Retraining classifier for user {} ...".format(u.pk)
                )
                call_command('train_classifiers', u.pk, '--exhaustive')
                u.profile.recent_interactions = 0
                u.profile.save()

                logger.info("Recalculating some old scores ...")
                self._reclassify_interacted_articles(u)

    
    def _retraining_permitted(self, user):
        """Checks whether enough articles have been clicked/liked/disliked
        that the user has reached the threshold for retraining."""
        # Total number of recommendations the user interacted with
        total_interactions = Recommendation.objects.filter(user=user).filter(
            Q(clicked=True) | Q(liked=True) | Q(disliked=True)
        ).count()

        # Use whichever threshold is lower
        threshold = min(
            self.RETRAINING_THRESHOLD_ABSOLUTE, 
            self.RETRAINING_THRESHOLD_PERCENT * total_interactions
        )

        return user.profile.recent_interactions >= threshold


    def _reclassify_interacted_articles(self, user):
        """Reclassify articles from within the last month which the user 
        clicked/liked/disliked."""
        last_month = datetime.date.today() - datetime.timedelta(days=30)
        interacted_articles_keys = Recommendation.objects\
            .filter(user=user)\
            .filter(article__pubdate__gte=last_month)\
            .filter(Q(clicked=True) | Q(liked=True) | Q(disliked=True))\
            .select_related('article')\
            .values_list('article__pk', flat=True)

        call_command('create_recommendations', 
            user_ids=[user.pk],
            article_ids=list(interacted_articles_keys)
        )