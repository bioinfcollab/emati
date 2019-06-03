#!/usr/bin/env python

from datetime import date, datetime
from pprint import pprint
import feedparser

from django.db.utils import IntegrityError
from django.conf import settings
from website.models import Article
from .abstractsource import AbstractSource
import re

import logging
logger = logging.getLogger(__name__)

class bioRxiv(AbstractSource):


    def __init__(self):
        super().__init__()

    def query_title(self, query, start_date=None, end_date=None, max_results=10):
        """Same as a normal query but restricts the search to only titles."""
        return self.query(query, max_results, restrict_title=True)

    def query(self, query, start_date=None, end_date=None, max_results=10, restrict_title=False):
        """ return nothing as bioRxiv RSS api, doesn't let us search by date"""
        return []


    def download(self, query, start_date=None, end_date=None):
        logger.info('self "{}" download "{}" start_date "{}" end_date "{}" ...'.format(self, query, start_date, end_date))
        """Similar to `query()` but saves all results to the database.

        In contrast to `query()` this doesn't return the articles. Instead
        they are processed in batches and saved to the database.
        """
        categories = [   'all',
                         'animal_behavior_and_cognition',
                         'biochemistry',
                         'bioengineering',
                         'bioinformatics',
                         'biophysics',
                         'cancer_biology',
                         'cell_biology',
                         'clinical_trials',
                         'developmental_biology',
                         'ecology',
                         'epidemiology',
                         'evolutionary_biology',
                         'genetics',
                         'genomics',
                         'immunology',
                         'microbiology',
                         'molecular_biology',
                         'neuroscience',
                         'paleontology',
                         'pathology',
                         'pharmacology_and_toxicology',
                         'physiology',
                         'plant_biology',
                         'scientific_communication_and_education',
                         'synthetic_biology',
                         'systems_biology',
                         'zoology',
                     ]
        # use just 3 category for testing
        # categories = [ 'all','zoology', 'systems_biology' ]

        num_new_results = 0
        num_integrity_errors = 0

        while categories:
            results, total_num_results = self._get_result_tuple(query, categories.pop())
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

            logger.info("  {}/{}".format(
                min(len(categories),total_num_results), total_num_results)
            )

        logger.info("Fetched {} new articles.".format(num_new_results))
        if num_integrity_errors > 0:
            msg = "Could not save {} articles. ".format(num_integrity_errors)
            msg += "They probably already existed in the database. "
            msg += "(IntegrityError)"
            logger.info(msg)


    def _get_result_tuple(self, search_query, category):
        logger.info('_get_result_tuple search_query "{}" category "{}" ...'.format(search_query,category))
        """
        Queries biorxiv.org and parses the returned results. Returns the
        dictionary containing the complete response. Returns a tuple of 
        (results, num_results), where `results` is a list of the results 
        returned in this batch and `num_results` is the total amount of
        results found for this query string.
        """
        url = (
            'http://connect.biorxiv.org/biorxiv_xml.php?subject='
              '{}'
        ).format(
             category
        )
        result_dict = feedparser.parse(url)
        if result_dict.get('status') != 200:
            logger.error("HTTP Error " + str(result_dict.get('status', 'no status')) + " in query")
            return None, None
        else:
            results = result_dict['entries']
            total_num_results = len(results)
            return results, total_num_results
    
    def _format_article(self, result):
        a = Article()
        a.title = result['title']
        a.abstract = result['description']
        a.journal = 'bioRxiv'
        a.url_source = result['link']
        a.pubdate = datetime.strptime(
            result['date'], '%Y-%m-%d'
        ).date()

        # Set a default value
        # Then try to override it with the PDF link
        a.url_fulltext = a.url_source
        for link in result['links']:
            if link.type == 'application/pdf':
                a.url_fulltext = link.href
        authors = []
        for author_list in [result['author']]:
            for author in author_list.split('., '):
                name = re.sub(',\s',',',author)
                # Here (?<=a)b is a positive lookbehind. It matches b following a
                # needed to add . where it is missing after .split('., ') above
                name = re.sub('(?<=[^\.])$','.',name)
                authors.append(name)
        a.authors_list = authors
        return a

if __name__ == '__main__':
    pass
