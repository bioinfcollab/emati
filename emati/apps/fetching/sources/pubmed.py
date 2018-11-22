#!/usr/bin/env python

import sys
import re
import time
import itertools
from Bio import Entrez, Medline
from requests import Timeout
from urllib3.exceptions import HTTPError
from socket import error as SocketError
from datetime import datetime, date

from django.db.utils import IntegrityError
from django.conf import settings

from website.models import Article

import logging
logger = logging.getLogger(__name__)


# Time between requests if any one fails
WAIT_SECONDS = 10

# Maximum number of times a request will be sent before considering it failed
# and returning nothing instead
MAX_NR_REQUESTS = 10



class Pubmed:


    def __init__(self):
        Entrez.email = settings.FETCHING_PUBMED_EMAIL
        Entrez.api_key = settings.FETCHING_PUBMED_API_KEY

        # Set batch size for downloading
        if settings.FETCHING_BATCH_SIZE:
            self.batch_size = settings.FETCHING_BATCH_SIZE
        else:
            self.batch_size = 1000


    def _compose_query(self, query, start_date=None, end_date=None):
        """Takes a query string and appends the required filters to it."""

        # Set end date to today if none was provided
        if end_date is None:
            end_date = date.today()

        # Only query with timespan if a start date was provided
        if start_date is not None:
            # Append timespan to the query string
            query += ' AND ' + self._get_time_span(start_date, end_date) + '[PDAT]'
        
        # Filter for articles that have links to full text and an abstract
        query += ' AND ("loattrfull text"[sb] AND hasabstract[text])'

        return query


    def query_title(self, query, start_date=None, end_date=None, max_results=10):
        """Same as a normal query but restricts the search to only titles."""
        query = query + '[TI]'
        return self.query(query, start_date, end_date, max_results)
        

    def query(self, query, start_date=None, end_date=None, max_results=10):
        """Retrieve articles from Pubmed for a given query string and time span.

        Omit the dates if you want to search in all papers. If only the 
        start_date is provided the end_date is set to the current day.
        Beware of queries with very large result sets since all results are
        loaded into memory. If you only want to load them into your database,
        use `download()` instead, which uses batch processing.

        Returns a list of articles. Each article is a dict with the following keys:
        title, abstract, journal, authors, url_fulltext, url_source, pubdate
        """

        # Append the timespan and some necessary filters to the query
        query = self._compose_query(query, start_date, end_date)
        
        # Get a list of ids
        idlist = self._fetch_ids(query)

        # Get the actual content for these ids
        records = self._fetch_papers(idlist)

        # Convert Pubmed records to our Article format
        articles = [self._format_article(r, start_date, end_date) for r in records]

        # format_article() could have returned None for an unfitting record
        articles = [a for a in articles if a is not None]

        return articles


    def download(self, query, start_date=None, end_date=None):
        """Similar to `query()` but saves all results to the database.

        In contrast to `query()` this doesn't return the articles. Instead they
        are processed in batches and saved to the database.
        """
        query = self._compose_query(query, start_date, end_date)
        idlist = self._fetch_ids(query)
        start = 0
        logger.info("Loading {} articles ...".format(len(idlist)))
        num_new_results = 0
        num_integrity_errors = 0
        while start < len(idlist):
            end = start + self.batch_size
            batch_ids = idlist[start:end]
            records = self._fetch_papers(batch_ids)
            for record in records:
                article = self._format_article(record, start_date, end_date)
                if article is not None:
                    try:
                        article.save()
                        num_new_results += 1
                    except IntegrityError:
                        # Uniqueness of articles is handled on database level.
                        # Do not warn about every single IntegrityError.
                        # Else they might flood the terminal messages.
                        num_integrity_errors += 1
            logger.info("  {}/{}".format(min(end, len(idlist)), len(idlist)))
            start += self.batch_size
        
        logger.info("Fetched {} new results.".format(num_new_results))
        if num_integrity_errors > 0:
            msg = "Could not save {} articles. ".format(num_integrity_errors)
            msg += "They probably already existed in the database. "
            msg += "(IntegrityError)"
            logger.info(msg)



    def _get_time_span(self, start_date, end_date):
        """Composes a time span in Pubmed-format from two dates.

        Returns a string representation of a time span in the format
        YYYY/MM/DD:YYYY/MM/DD (E.g.:'2018/06/10:2018/06/25').
        """
        start_string = date.strftime(start_date, '%Y/%m/%d')
        end_string = date.strftime(end_date, '%Y/%m/%d')
        return start_string + ":" + end_string


    def _extract_pubdate(self, record, start_date, end_date):
        """Extracts an article's date of publication.
        
        start_date and end_date are required to check the validity of the
        retrieved time span. This ensures that the date of publication
        always lies within the queried time span.

        Returns:
            A datetime.date object representing the day of publication.
        """

        try:
            # Use the 'Date of Electronic Publication'
            # (date the publisher made an electronic version of the article available)
            date_dep = datetime.strptime(record['DEP'], '%Y%m%d').date()
            if start_date and start_date <= date_dep and date_dep <= end_date:
                return date_dep
        except:
            # The record either didn't contain a DEP or
            # the DEP was for some reason not within our queried timespan 
            pass

        try:
            # Use the 'Date of Publication'
            # (full date on which the issue of the journal was published)
            date_dp = datetime.strptime(record['DP'], '%Y %b %d').date()
            if start_date and start_date <= date_dp and date_dp <= end_date:
                return date_dp
        except:
            # Didn't contain a DP or the DP was not within our queried timespan
            pass

        # Could not extract the correct date
        # Fall back to the end of our queried timespan
        return end_date



    def _format_article(self, record, start_date, end_date):
        """Reformats a Pubmed record into an instance of our Article model.

        A pubmed record contains information we don't need, or need in a
        different format. This function restructures everything to fit our
        desired format. These changes are:
        - Use the full journal name (['JT']) but only keep everything before the
          first colon (':'). Sometimes the full journal title can be very long.
          In these cases additional descriptions are separated by a colon. E.g.:
          European archives of oto-rhino-laryngology : official journal of the
          European Federation of Oto-Rhino-Laryngological Societies (EUFOS) :
          affiliated with the German Society for Oto-Rhino-Laryngology - Head
          and Neck Surgery
        - Convert the list of authors into a string of semicolon-separated pairs
          of surname and name. E.g. 'Doe,John;Mustermann,Max;Smitherson,Smithy'

        Returns an instance of website.models.Article
        """

        # Alternative fields:
        # ['TA'] - journal abbreviation (E.g. 'Angew Chem Int Ed Engl')
        # ['AU'] - short author (last name + initials)
        
        a = Article()
        try:
            a.title = record['TI']
            a.abstract = record['AB']
            a.journal = record['JT']
            a.authors_list = record['FAU']
            a.url_fulltext = self._get_fulltext_url(record)
            a.url_source = self._get_source_url(record)
            a.pubdate = self._extract_pubdate(record, start_date, end_date)
            return a
        except KeyError:
            # Some field could not be supplied
            # Hence this record cannot be used
            return None


    def _get_source_url(self, record):
        """Returns the URL to this article's Pubmed page."""
        return 'http://www.ncbi.nlm.nih.gov/pubmed/' + str(record['PMID'])

    
    def _get_fulltext_url(self, record):
        """Returns the URL to this article's fulltext.

        The URL is the Entrez eLink utility which will then redirect to the
        fulltext website. Note that we therefore cannot guarantee that this
        URL will link to a full text. If an article has no fulltext this URL
        will simply redirect to its Pubmed page.
        """
        # cmd=llinks   Get the primary LinkOut provider
        # retmode=ref  Directly redirect to the first URL that would be returned
        return 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi?dbfrom=pubmed&cmd=prlinks&retmode=ref&id=' + str(record['PMID'])


    def _fetch_ids(self, query):
        """Queries Pubmed and returns the list of PMIDs."""
        logger.info('Querying Pubmed for "{}" ...'.format(query))
        for _ in range(MAX_NR_REQUESTS):
            try:
                handle = Entrez.esearch(db="pubmed", term=query, retmax=100000000)

                record = Entrez.read(handle)
                
                logger.info('Found {} PMIDs.'.format(len(record["IdList"])))
                return record["IdList"]
            except (Timeout, HTTPError, SocketError):
                logger.warning("An error occured while fetching Pubmed IDs. Trying again in {} seconds.".format(WAIT_SECONDS))
                time.sleep(WAIT_SECONDS)


    def _fetch_papers(self, pmid_list):
        """Loads the papers for a given list of PMIDs.
        Returns a list of all found pubmed records.
        """
        # Efetch can only handle retmax = 10000
        # Keep retmax constant and iterate over retstart
        start = 0
        step_size = 10000
        records = []
        while start < len(pmid_list):
            try:
                # Get the articles from pubmed
                handle = Entrez.efetch(
                    db="pubmed", id=pmid_list, rettype="medline", 
                    retmode="text", retstart=start, retmax=step_size
                )

                parsed_results = Medline.parse(handle)
                records += list(parsed_results)

                start += step_size
            except (Timeout, HTTPError, SocketError, RuntimeError):
                logger.warning("An error occured while fetching Pubmed records. Trying again in 10 seconds.", exc_info=True)
                # Wait a bit to avoid sending too many requests
                time.sleep(10)
        return records


    def _find_full_text(self, records):
        """Finds the URL to the fulltext for a list of records.

        NOTE: This is pretty slow. It sends requests to the Entrez eLink utility
        in batches of 10000 PMIDs. The result is pretty large since it contains
        a lot of overhead. Parsing this can take a couple of minutes for each
        batch. If instead redirecting the user at runtime via Pubmed is
        acceptable then consider using _get_fulltext_url().

        Args:
            records (array): An array of records. Each record is a dictionary
                holding several kinds of information about the article. Make
                sure that at least the field 'PMID' is available. Else it
                won't work.

        Returns:
            The same array of records, but now each has an additional field
            called 'url_fulltext'.
        """

        # Map the PMID to each record so we can look them up faster
        record_map = {r['PMID']:r for r in records}

        idlist = [r["PMID"] for r in records]
        length = len(idlist)
        logger.info("Loading full text links for {} articles ...".format(length))

        counter = 0
        step_size = 10000
        while idlist:
            slist = idlist[:step_size]
            del idlist[:step_size]
            while True:
                try:
                    handle = Entrez.elink(db="pubmed", id=slist, cmd="prlinks", retmode="xml")
                    break
                except (Timeout, HTTPError, SocketError, RuntimeError):
                    logger.warning("Error while loading articles. Trying again in {} seconds.".format(WAIT_SECONDS), exc_info=True)
                    time.sleep(WAIT_SECONDS)
            
            root = Entrez.read(handle)
            for r in root:
                mylist = r["IdUrlList"]["IdUrlSet"]
                if mylist[0]:
                    pmid = mylist[0]["Id"]
                    if mylist[0]["ObjUrl"]:
                        pmid_url = mylist[0]["ObjUrl"][0]["Url"]

                        rec = record_map[pmid]
                        rec['url_fulltext'] = pmid_url

            # Print the progress
            counter += step_size
            counter = min(counter, length)
            logger.info('  {}/{}'.format(counter, length))

        return record_map.values()


if __name__ == "__main__":
    pass
