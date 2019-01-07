from datetime import datetime, date, timedelta
from argparse import ArgumentTypeError

from django.core.management.base import BaseCommand, CommandError
from django.db.utils import IntegrityError
from fetching import Fetcher

import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Calculate scores for recommendations for given users and articles.'
    date_format = '%Y-%m-%d'

    def valid_date(self, s):
        try:
            return datetime.strptime(s, "%Y-%m-%d")
        except ValueError:
            msg = "Not a valid date: '{0}'.".format(s)
            raise ArgumentTypeError(msg)


    def add_arguments(self, parser):
        parser.add_argument(
            '--last-day',
            action='store_true',
            help=""
        )
        parser.add_argument(
            '--last-week',
            action='store_true',
            help=""
        )
        parser.add_argument(
            '--start-date', '-s',
            type=self.valid_date,
            help=(
                "Use this to specify a custom time span from which all "
                "papers will be downloaded. Date format: YYYY-MM-DD. "
                "Large time spans will be fetched in chunks of one week."
            )
        )
        parser.add_argument(
            '--end-date', '-e',
            type=self.valid_date,
            help=(
                "Format YYYY-MM-DD. Use this in combination with "
                "--start-date to download papers from a custom time span. "
                "If a start-date is provided but no end-date, the end-date "
                "will be set to the current day."
            )
        )


    def handle(self, *args, **options):
        """The main entry point for this command."""

        fetcher = Fetcher()

        if options['last_day']:
            fetcher.download_last_day()
        elif options['last_week']:
            fetcher.download_last_week()
        elif options['start_date']:
            start_date = options['start_date'].date()
            if options['end_date']:
                end_date = options['end_date'].date()
            else:
                end_date = date.today()

            if end_date < start_date:
                self.stderr.write("The start date must lie before the end date.")
                return

            # Break down large time spans into week-batches
            while start_date < end_date:
                batch_end = min(start_date + timedelta(days=6), end_date)
                fetcher.download("", start_date, batch_end)
                start_date += timedelta(days=7)
            return

        else:
            self.stderr.write("Nothing was fetched. No time span was specified.")