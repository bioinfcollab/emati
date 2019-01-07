"""AbstractSource class

Inherit from this class to implement a new source for articles.
"""

from django.conf import settings


class AbstractSource:


    def __init__(self):
        # Set batch size for downloading
        if settings.FETCHING_BATCH_SIZE:
            self.batch_size = settings.FETCHING_BATCH_SIZE
        else:
            self.batch_size = 1000


    def query(self, query, start_date=None, end_date=None, max_results=10):
        raise NotImplementedError("The 'query' method was not implemented.")


    def query_title(self, query, start_date=None, end_date=None, max_results=10):
        raise NotImplementedError("The 'query_title' method was not implemented.")


    def download(self, query, start_date=None, end_date=None):
        raise NotImplementedError("The 'download' method was not implemented.")