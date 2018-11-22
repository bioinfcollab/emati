import datetime

from django.core.management.base import BaseCommand, CommandError
from website import search

import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Rebuild the search index from scratch.'

    def handle(self, *args, **options):
        """The main entry point for this command."""
        search.rebuild_index()