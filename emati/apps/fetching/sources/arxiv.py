#!/usr/bin/env python

from datetime import date, datetime
from pprint import pprint
import feedparser

from django.db.utils import IntegrityError
from django.conf import settings
from website.models import Article
from .abstractsource import AbstractSource

import logging
logger = logging.getLogger(__name__)


class Arxiv(AbstractSource):


    def __init__(self):
        super().__init__()
    

    def _compose_query(self, query, start_date=None, end_date=None):
        """Takes a query string and appends the required filters to it."""

        # Set end date to today if none was provided
        if end_date is None:
            end_date = date.today()

        # Only query with timespan if a start date was provided
        if start_date is not None:
            if query:
                query += '+AND+'
            else:
                query = ''

            # timerange-format: 'submittedDate:[201807010000+TO+201807082359]'
            query += (
                'submittedDate:['
                + datetime.strftime(start_date, '%Y%m%d0000')
                + '+TO+'
                + datetime.strftime(end_date, '%Y%m%d2359')
                + ']'
            )
        
        return query
    

    def query_title(self, query, start_date=None, end_date=None, max_results=10):
        """Same as a normal query but restricts the search to only titles."""
        return self.query(query, start_date, end_date, max_results, restrict_title=True)


    def query(self, query, start_date=None, end_date=None, max_results=10, restrict_title=False):
        """Retrieve articles from arXiv for a given query string and time span.

        Omit the dates if you want to search in all papers. If only the
        start_date is provided the end_date is set to the current day. Beware
        of queries with very large result sets since all results are loaded
        into memory. If you only want to load them into your database, use
        `download()` instead, which uses batch processing.

        Set `restrict_title` to True if you only want to search in article
        titles.

        Returns a list of articles. Each article is an instance of
        website.models.Article, but is not saved yet.
        """
        if restrict_title:
            search_type = 'all'
        else:
            search_type = 'title'

        query = self._compose_query(query, start_date, end_date)
        results = self._get_result_dict(
            query, start=0, max_results=max_results, search_type=search_type
        )['entries']

        articles = []
        for result in results:
            articles.append(self._format_article(result))

        return articles

    
    def download(self, query, start_date=None, end_date=None):
        """Similar to `query()` but saves all results to the database.

        In contrast to `query()` this doesn't return the articles. Instead
        they are processed in batches and saved to the database.
        """
        query = self._compose_query(query, start_date, end_date)
        logger.info('Querying for "{}" ...'.format(query))

        start = 0
        result_dict = self._get_result_dict(
            query, start=start, max_results=self.batch_size
        )
        if result_dict is None:
            logger.info("No results")

        results = result_dict['entries']
        total_num_results = int(result_dict['feed']['opensearch_totalresults'])
        num_new_results = 0
        num_integrity_errors = 0
        while results:
            for result in results:
                article = self._format_article(result)
                if article is not None:
                    try:
                        article.save()
                        num_new_results += 1
                    except IntegrityError:
                        # Uniqueness of articles is handled on database level.
                        # Do not warn about every single IntegrityError.
                        # Else they might flood the terminal messages.
                        num_integrity_errors += 1

            start += self.batch_size
            results = self._get_result_dict(
                query, start=start, max_results=self.batch_size
            )['entries']

            logger.info("  {}/{}".format(
                min(start, total_num_results), total_num_results)
            )

        logger.info("Fetched {} new articles.".format(num_new_results))
        if num_integrity_errors > 0:
            msg = "Could not save {} articles. ".format(num_integrity_errors)
            msg += "They probably already existed in the database. "
            msg += "(IntegrityError)"
            logger.info(msg)


    def _get_result_dict(self, search_query, id_list=[], start=0, max_results=10, 
                     sort_by='relevance', sort_order='descending', 
                     search_type='all'):
        """
        Queries arxiv.org and parses the returned results. Returns the
        dictionary containing the complete response. The total number of
        available records will be stored in
        ['feed']['opensearch_totalresults'] while the list of actually
        returned records is stored in ['entries']. Returns None if no results
        were found for this search request.
        """
        url = (
            'http://export.arxiv.org/api/query?'
            'search_query={}&'
            'search_type={}&'
            'id_list={}&'
            'start={}&'
            'max_results={}&'
            'sort_by={}&'
            'sort_order={}'
        ).format(
            search_query,
            search_type,
            ','.join(id_list), 
            start, 
            max_results, 
            sort_by, 
            sort_order
        )
        results = feedparser.parse(url)
        if results.get('status') != 200:
            logger.error("HTTP Error " + str(results.get('status', 'no status')) + " in query")
            return None
        else:
            return results

    
    def _format_article(self, result):
        a = Article()
        a.title = result['title']
        a.abstract = result['summary']
        a.journal = 'arXiv'
        a.url_source = result['link']
        a.pubdate = datetime.strptime(
            # Given format: 2018-03-02T15:27:39Z
            result['published'].split('T')[0], '%Y-%m-%d'
        ).date()

        # Set a default value
        # Then try to override it with the PDF link
        a.url_fulltext = a.url_source
        for link in result['links']:
            if link.type == 'application/pdf':
                a.url_fulltext = link.href

        authors = []
        for author in result['authors']:
            names = author['name'].split()
            last_name = names[-1]
            first_name = ' '.join(names[:-1])
            authors.append(last_name + ',' + first_name)
        a.authors_list = authors

        return a


if __name__ == '__main__':
    pass