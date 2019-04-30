from datetime import datetime, date, timedelta

from django.utils import timezone
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from allauth.account.models import EmailAddress

from dashboard.models import WeekStat
from website.models import UserLog, Article, Recommendation

import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Creates a stastics entry for the past seven days. '
        'Ideally this is called at the same time every week.'
    )


    def handle(self, *args, **options):
        """The main entry point for this command."""
        start_date = datetime.now() - timedelta(days=7)
        start_date = timezone.make_aware(start_date)

        s = WeekStat(
            num_registered_users = self.get_registered_users(),
            num_verified_users = self.get_verified_users(),
            num_active_users = self.get_active_users(start_date),
            num_returning_users = self.get_returning_users(),
            num_search_requests = self.get_search_requests(start_date),
            num_users_searched = self.get_users_searched(start_date),
            num_likes = self.get_likes(start_date),
            num_dislikes = self.get_dislikes(start_date),
            num_clicks = self.get_clicks(start_date),
            num_articles_only_clicked = self.get_only_clicked(start_date),
            num_articles_clicked_liked = self.get_clicked_liked(start_date),
            num_articles_clicked_disliked = self.get_clicked_disliked(start_date),
            num_articles = self.get_articles(),
            num_recommendations = self.get_recommendations(),
        )

        s.save()
        logger.info(
            "Successfully calculated statistics for days from "
            + date.strftime(start_date, '%Y-%m-%d')
            + " to "
            + date.strftime(date.today(), '%Y-%m-%d')
        )


    def get_registered_users(self):
        """Returns the number of all users stored in the database."""
        return User.objects.all().count()


    def get_verified_users(self):
        """Returns the number of users that have verified their email."""
        return len(EmailAddress.objects\
            .filter(verified=True)\
            .values_list('user', flat=True)\
            .distinct())


    def get_active_users(self, after):
        """Returns the amount of users that were active after a 
        certain date."""
        return UserLog.objects\
            .filter(timestamp__gte=after)\
            .values_list('user', flat=True)\
            .distinct()\
            .count()


    def get_returning_users(self):
        """Returns the amount of users that were active in 
        two consecutive weeks."""
        lastweek = datetime.now() - timedelta(days=7)
        lastweek = timezone.make_aware(lastweek)
        weekbeforelast = datetime.now() - timedelta(days=14)
        weekbeforelast = timezone.make_aware(weekbeforelast)

        # Get a list of active users from the past week
        users_lastweek = UserLog.objects\
            .filter(timestamp__gte=lastweek)\
            .values_list('user', flat=True)\
            .distinct()

        # Get a list of active users from the week before last
        users_weekbeforelast = UserLog.objects\
            .filter(timestamp__lte=lastweek)\
            .filter(timestamp__gte=weekbeforelast)\
            .values_list('user', flat=True)\
            .distinct()
        
        # Get those users that appear in both lists
        intersection = [u for u in users_lastweek if u in users_weekbeforelast]
        return len(intersection)

    
    def get_clicks(self, after):
        """Returns the number of clicks that occured after a given date."""
        return UserLog.objects\
            .filter(timestamp__gte=after)\
            .filter(event=UserLog.Events.CLICK)\
            .count()


    def get_likes(self, after):
        """Returns the number of likes that occured after a given date."""
        return UserLog.objects\
            .filter(timestamp__gte=after)\
            .filter(event=UserLog.Events.LIKE)\
            .count()


    def get_dislikes(self, after):
        """Returns the number of dislikes that occured after a given date."""
        return UserLog.objects\
            .filter(timestamp__gte=after)\
            .filter(event=UserLog.Events.DISLIKE)\
            .count()


    def get_only_clicked(self, after):
        """Returns the number of articles that were clicked 
        but neither liked nor disliked."""
        return Recommendation.objects\
            .filter(article__pubdate__range__gte=after)\
            .filter(clicked=True)\
            .filter(liked=False)\
            .filter(disliked=False)\
            .count()

    
    def get_clicked_liked(self, after):
        """Returns the number of recommendations that were 
        clicked AND liked after a given date."""
        return Recommendation.objects\
            .filter(article__pubdate__range__gte=after)\
            .filter(clicked=True)\
            .filter(liked=True)\
            .count()


    def get_clicked_disliked(self, after):
        """Returns the number of recommendations that were 
        clicked AND disliked after a given date."""
        return Recommendation.objects\
            .filter(article__pubdate__range__gte=after)\
            .filter(clicked=True)\
            .filter(disliked=True)\
            .count()


    def get_search_requests(self, after):
        """Returns the number of search requests submitted after 
        a specific date."""
        return UserLog.objects\
            .filter(timestamp__gte=after)\
            .filter(event=UserLog.Events.SEARCH)\
            .count()

        
    def get_users_searched(self, after):
        """Returns the amount of users that searched at least once 
        after a specific date."""
        return len(UserLog.objects\
            .filter(timestamp__gte=after)\
            .filter(event=UserLog.Events.SEARCH)\
            .values_list('user', flat=True)\
            .distinct())


    def get_articles(self):
        """Returns the current number of articles in the database."""
        return Article.objects.all().count()


    def get_recommendations(self):
        """Returns the current number of recommendations in the database."""
        return Recommendation.objects.all().count()
