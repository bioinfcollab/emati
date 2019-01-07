from datetime import datetime, date, timedelta
from argparse import ArgumentTypeError

from django.core.management.base import BaseCommand, CommandError
from django.db.utils import IntegrityError
from website import search

import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update the search index with new files from the database.'

    def valid_date(self, s):
        try:
            return datetime.strptime(s, "%Y-%m-%d")
        except ValueError:
            msg = "Not a valid date: '{0}'.".format(s)
            raise ArgumentTypeError(msg)

    def add_arguments(self, parser):
        parser.add_argument(
            '--last-week',
            action='store_true',
            help="Only index articles that were published during the last week."
        )
        parser.add_argument(
            '--last-day',
            action='store_true',
            help="Only index articles that were published during the last day."
        )
        parser.add_argument(
            '--last-month',
            action='store_true',
            help="Only index articles that were published during the last month."
        )
        parser.add_argument(
            '--start-date', '-s',
            type=self.valid_date,
            help=(
                "Only index articles published after this date (YYYY-MM-DD)."
            )
        )
        parser.add_argument(
            '--end-date', '-e',
            type=self.valid_date,
            help=(
                "Only index articles published before this date (YYYY-MM-DD)."
            )
        )


    def handle(self, *args, **options):
        """The main entry point for this command."""
        start = None
        end = None
        if options['last_day']:
            start = date.today() - timedelta(days=1)
        elif options['last_week']:
            start = date.today() - timedelta(days=7)
        elif options['last_month']:
            start = date.today() - timedelta(days=30)
        else:
            if options['start_date']:
                start = options['start_date'].date()
            if options['end_date']:
                end = options['end_date'].date()
        search.update_index(start_date=start, end_date=end)
