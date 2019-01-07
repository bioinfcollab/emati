"""A module to search for articles in an elasticsearch index

"""

from datetime import date

import elasticsearch
import elasticsearch.helpers
from django.conf import settings

from .models import Article


import logging
logger = logging.getLogger(__name__)


# Get the global client
es = settings.WEBSITE_SEARCH_CLIENT

# Batch size when updating the index
UPDATE_BATCH_SIZE = 1000


def fulltext_search(query_string, offset=0, max_results=10):
    """Search the index for articles matching in title or abstract.

    Args:
        query_string (string): the search query.
        max_results (int): maximum number of results to return.

    Returns: a list of articles.
    """

    if query_string is None:
        # Just return everything if no query was provided
        query = {'query': {'match_all': {}}, 'size': max_results}
    else:
        # Search in title and abstract
        query = {
            'query': {
                'query_string': {
                    'fields': ['title', 'abstract'],
                    'query': query_string,
                    'default_operator': 'AND'
                }
            },
            'highlight': {
                'fields': {
                    'title': {
                        'number_of_fragments': 0
                    },
                    'abstract': {}
                }
            },
            'from': offset,
            'size': max_results
        }
    result = es.search(index=settings.WEBSITE_SEARCH_INDEX, body=query)
    articles = []
    for hit in result['hits']['hits']:
        a = _to_article(hit)
        if a is not None:
            articles.append(a)
    total_results = result['hits']['total']
    return total_results, articles
        

def update_index(start_date=None, end_date=None):
    """Update the index with articles from the database. Use start_date and 
    end_date to restrict the time range. If no date is specified, all
    articles found in the database will be reindex.

    Args:
        start_date (date): Only update articles published after this date.
        end_date (date): Only index articles published before this date.
    """

    articles = Article.objects.all()
    if start_date is not None:
        articles = articles.filter(pubdate__gte=start_date)
    if end_date is not None:
        articles = articles.filter(pubdate__lte=end_date)

    # Make sure articles are ordered or else we risk
    # getting the same article in different batches
    articles = articles.order_by('pk')

    logger.info("Updating the search index ...")

    total = articles.count()
    for start in range(0, total, UPDATE_BATCH_SIZE):
        end = min(start + UPDATE_BATCH_SIZE, total)
        batch = articles[start:end]
        elasticsearch.helpers.bulk(es, doc_gen(batch))
        logger.info("  {}/{}".format(end, total))


def doc_gen(articles):
    """A generator of JSON-formatted articles.
    
    Used by bulk indexing. Takes a list of articles and returns
    them as indexing operations for elasticsearch.
    """
    for article in articles:
        doc = {}
        doc['_op_type'] = 'index'
        doc['_index'] = settings.WEBSITE_SEARCH_INDEX
        doc['_type'] = 'article'
        doc['_id'] = article.pk
        doc['_source'] = _to_doc(article)
        yield doc


def delete_index():
    """Deletes the currently used index."""
    try:
        logger.info("Deleting the search index ...")
        es.indices.delete(index=settings.WEBSITE_SEARCH_INDEX)
    except elasticsearch.exceptions.NotFoundError:
        logger.info("Nothing to delete")


def rebuild_index():
    """Rebuild the index from scratch.

    This corresponds to calling `delete_index()` and `update_index()`.
    """
    delete_index()
    update_index()


def _to_doc(article):
    """Converts an article to the JSON format used by elasticsearch."""
    doc = {
        'title': article.title,
        'abstract': article.abstract,
        'journal': article.journal,
        'authors_string': article.authors_string,
        'pubdate': article.pubdate,
        'url_fulltext': article.url_fulltext
    }
    return doc


def _to_article(hit):
    """Converts a search result hit into an Article object."""
    try:
        article = Article()
        article.pk = hit['_id']
        article.title = hit['_source']['title']
        article.abstract = hit['_source']['abstract']
        article.journal = hit['_source']['journal']
        article.authors_string = hit['_source']['authors_string']
        article.pubdate = hit['_source']['pubdate']
        article.url_fulltext = hit['_source']['url_fulltext']
    except KeyError:
        return None

    try:
        article.abstract_highlighted = ' ... '.join(hit['highlight']['abstract'])
    except KeyError:
        article.abstract_highlighted = None

    try:
        article.title_highlighted = hit['highlight']['title'][0]
    except KeyError:
        article.title_highlighted = None
        
    return article