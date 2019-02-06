from datetime import datetime, timedelta

from django.utils import timezone
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

import logging
logger = logging.getLogger(__name__)



class Command(BaseCommand):
    help = """Deletes users that have been inactive for too long. Will not 
    delete staff users and admins. By default an account is considered 
    'inactive' if the user's last visit was more than a year ago."""


    def add_arguments(self, parser):
        parser.add_argument('-d', '--days', 
            type=int,
            nargs='?',
            default=365,
            help="""The amount of inactive days before an account is 
            considered inactive and will be deleted. Defaults to 365 days."""
        )


    def handle(self, *args, **options):
        """The main entry point for this command."""

        # Everything older than this date is considered inactive
        threshold_date = timezone.now() - timedelta(days=options['days'])
        logger.info(
            "Deleting users that were last active before {}".format(
                datetime.strftime(threshold_date, '%Y-%m-%d')
            )
        )

        deletion_counter = 0
        for u in User.objects.all():

            # Never delete staff users and admins
            if u.is_staff or u.is_superuser:
                continue

            if u.profile.last_visit and u.profile.last_visit < threshold_date:
                logger.info("Deleting user {}".format(u.pk))
                u.delete()
                deletion_counter += 1

        logger.info("Deleted {} inactive accounts".format(deletion_counter))


