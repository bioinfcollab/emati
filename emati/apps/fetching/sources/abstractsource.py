"""AbstractSource class

Inherit from this class to implement a new source for articles.

"""



from abc import ABC, abstractmethod


MANDATORY_KEYS = set([
    'title', 
    'abstract', 
    'journal', 
    'authors', 
    'url_fulltext', 
    'url_source', 
    'pubdate'
])


class AbstractSource(ABC):


    def query(self, query_string, date_start, date_end):
        """Query for a given query string within a time span.

        Args:
            query_string (string): The query string that is passed on to Pubmed.
            date_start (date): The beginning of the time span limitting the query.
                Omit this to search in all papers.
            date_end (date): The end of the time span limitting the query.
                Defaults to current date.
        """
        articles = self.__get_articles(query_string, date_start, date_end)
        valid_articles = [a for a in articles if __is_valid(a)]
        return articles


    def __is_valid(article):
        """Checks if an article contains all mandatory fields"""
        return set(article.get_keys()) == MANDATORY_KEYS


    @abstractmethod
    def __get_articles(self, query_string, date_start=None, date_end=None):
        """Overwrite this to implement your source-specific behavior."""
        pass