import os
import re
from django import template
from django.conf import settings
from django.http import QueryDict
from django.utils.html import escape
from django.urls import reverse

register = template.Library()


@register.filter
def highlight_escape(string):
    """Performs Django's html escaping but keeps the <em></em> tags 
    that are required for highlighting of search results."""
    safe_string = escape(string)
    safe_string = safe_string.replace('&lt;em&gt;', '<em>')
    safe_string = safe_string.replace('&lt;/em&gt;', '</em>')
    return safe_string


@register.filter
def format_authors(authors):
    """Reduces a list of names to a short string (possibly with ellipses)."""

    # Defines how an author's name is displayed
    def prepare_author(a):
        # Prints authors as e.g. "Schroeder M"
        try:
            lastname, firstname = a.split(',')
        except ValueError:
            try:
                lastname, firstname = a.split(' ')
            except ValueError:
                return a
        return lastname.strip() + ' ' + firstname.strip()[0]

    authors = [prepare_author(a) for a in authors]

    # Maximum number of authors to display before replacing
    # names with ellipses
    MAX_AUTHORS = 4

    # Display as many authors as allowed, followed by
    # ellipses (...) and ALWAYS the last author.
    if len(authors) <= MAX_AUTHORS:
        return ', '.join(authors)
    else:
        output = ', '.join(authors[:MAX_AUTHORS-2])
        output += ', ... , '
        output += authors[-1]
        return output
        

@register.filter
def format_authors_verbose(authors):
    if not isinstance(authors, list):
        authors = authors.split(';')
    for i in range(len(authors)):
        try:
            lastname, firstname = authors[i].split(',')
            authors[i] = firstname + ' ' + lastname
        except ValueError:
            # Just use the name as it is
            pass
    return ', '.join(authors)
    

@register.filter
def format_abstract(abstract):
    """Extracts a short excerpt from an abstract."""

    # Match everything behind either CONCLUSION or CONCLUSIONS
    m = re.search(r'((?<=CONCLUSION: )|(?<=CONCLUSIONS: )).+', abstract)

    # Check if there is a match
    if m:
        return m.group()

    # When there's no match
    else:
        # Get the last couple of sentences
        pattern = re.compile('(?<=\.) (?=.)')
        sentences = pattern.split(abstract)

        excerpt = ""
        while len(excerpt) < settings.WEBSITE_ABSTRACT_LENGTH and sentences != []:

            # Start fresh if certain terms are encountered (everything after them is boring)
            if sentences[-1].lower().startswith(("(c) ", "supplementary information", "contact", "availability")) \
            or "is available at" in sentences[-1].lower() \
            or "is available freely" in sentences[-1].lower() \
            or "is available through" in sentences[-1].lower() \
            or "is freely available through" in sentences[-1].lower() \
            or "is accessible from" in sentences[-1].lower():
                excerpt = ""
            elif sentences[-1].find("www.") != -1 or sentences[-1].find("http://") != -1:
                # we dont want links in our conclusion, often not interesting
                excerpt = ""
            else:
                # Add another sentence to the excerpt's front
                excerpt = sentences[-1] + ' ' + excerpt
            del sentences[-1]

        return excerpt


@register.filter
def format_journal(journal):
    """Removes translations or additional info from long journal names."""
    # Some examples we want to avoid:
    # Zhonghua zhong liu za zhi [Chinese journal of oncology]
    # Biomedicine & pharmacotherapy = Biomedecine & pharmacotherapie

    # Take everything in front of delimiting characters
    journal = journal.split(':')[0]
    journal = journal.split('=')[0]
    
    # Remove everything in matching brackets
    journal = re.sub(r'\(.*?\)', '', journal)
    journal = re.sub(r'\[.*?\]', '', journal)

    # Remove whitespace from ends of string
    journal = journal.strip()
    return journal
    

@register.filter
def format_score(score):
    """Takes a float between 0 and 1. Returns a probability as a string between "0%" and "100%"."""
    return '{:.0f}%'.format(score * 100)


@register.filter
def basename(path):
    """Splits a path and returns only the files basename."""
    return os.path.basename(path)


@register.filter
def human_readable(size):
    """Converts a size in bytes into a human readble format (e.g. 2.0KB)"""
    
    # Ensure we're dealing with a number
    size = int(size)

    if size < 512000:
        size = size / 1024.0
        ext = ' KB'
    elif size < 4194304000:
        size = size / 1048576.0
        ext = ' MB'
    else:
        size = size / 1073741824.0
        ext = ' GB'
    return '{}{}'.format(str(round(size, 2)), ext)
    

@register.simple_tag
def active(request, *patterns):
    """Searches for a set of patterns in the current URL.
    Returns the string '-active' if one was found.

    This tag is used by the navigation bar to change the
    respective 'nav-item' into a 'nav-item-active'.
    """
    for pattern in patterns:
        if re.search(pattern, request.path):
            return '-active'
    return ''
