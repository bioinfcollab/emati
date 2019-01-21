from django.db.utils import IntegrityError
from django.conf import settings

import importlib
from datetime import date, timedelta
from website.models import Article

import logging
logger = logging.getLogger(__name__)


class Fetcher:
    """Loads articles from various sources and stores them in a database."""

    def __init__(self):
        self.sources = []

        # Instantiate all sources defined in the settings
        for s in settings.FETCHING_SOURCES:

            # Split into module and class
            m, c = s.rsplit('.', 1)

            # Import module and instantiate class
            module = importlib.import_module(m) 
            class_ = getattr(module, c)
            instance = class_()

            self.add_source(instance)


    def add_source(self, source):
        self.sources.append(source)
        

    def download_last_day(self):
        """Loads yesterday's papers from all sources
        and saves them in the database.
        """
        self.download("", date.today(), date.today())

    
    def download_last_week(self):
        """Loads last week's articles from all sources into our database."""
        last_week = date.today() - timedelta(days=7)
        self.download("", last_week, date.today())
        
    
    def download(self, query, start_date=None, end_date=None):
        """Searches all sources for the given query string. Stores articles 
        in the database. The searched time span can be limited via 
        `start_date` and `end_date`."""
        for s in self.sources:
            s.download(query, start_date, end_date)

    
    def query(self, query, start_date=None, end_date=None, max_results=10):
        """Query all sources for a given query string."""
        articles = []
        for s in self.sources:
            articles += s.query(
                query, 
                start_date=start_date, 
                end_date=end_date, 
                max_results=max_results
            )
        return articles

    
    def query_title(self, query, start_date=None, end_date=None, max_results=10):
        """Query all sources for a query string but only look at titles."""
        articles = []
        for s in self.sources:
            articles += s.query_title(
                query, 
                start_date=start_date, 
                end_date=end_date, 
                max_results=max_results
            )
        return articles

