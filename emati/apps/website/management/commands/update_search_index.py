import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db.utils import IntegrityError
from website import search

import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update the search index with new files from the database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--last-week',
            action='store_true',
            help=""
        )
        parser.add_argument(
            '--last-day',
            action='store_true',
            help=""
        )


    def handle(self, *args, **options):
        """The main entry point for this command."""
        if options['last_day']:
            after = datetime.date.today() - datetime.timedelta(days=1)
        elif options['last_week']:
            after = datetime.date.today() - datetime.timedelta(days=7)
        else:
            after = None
        search.update_index(only_after=after)