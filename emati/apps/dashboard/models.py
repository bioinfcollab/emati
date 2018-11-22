from django.db import models

# save weekly statistics so we don't have to recalculate it for every request

class WeekStat(models.Model):
    """A summary of user statistics for one week."""
    timestamp = models.DateTimeField(auto_now_add=True)
    num_registered_users = models.IntegerField(default=0)
    num_verified_users = models.IntegerField(default=0)
    num_active_users = models.IntegerField(default=0)
    num_returning_users = models.IntegerField(default=0)
    num_search_requests = models.IntegerField(default=0)
    num_users_searched = models.IntegerField(default=0)
    num_likes = models.IntegerField(default=0)
    num_dislikes = models.IntegerField(default=0)
    num_clicks = models.IntegerField(default=0)
    num_articles_only_clicked = models.IntegerField(default=0)
    num_articles_clicked_liked = models.IntegerField(default=0)
    num_articles_clicked_disliked = models.IntegerField(default=0)
    num_articles = models.IntegerField(default=0)
    num_recommendations = models.IntegerField(default=0)

    class Meta:
        get_latest_by = 'timestamp'

        # Order by oldest first
        ordering = ['timestamp']
