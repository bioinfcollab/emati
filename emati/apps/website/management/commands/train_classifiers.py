import os
import io
import re
import random
import numpy as np
import itertools
import bibtexparser
import RISparser
import xml.etree.ElementTree as ET

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.contrib.auth.models import User

from machinelearning.trainer import Trainer
from machinelearning.utils import Targets, prepare_article
from fetching import Fetcher
from website.models import Article, Classifier, UserUpload, UserTextInput

import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '(Re)train the classifier for the specified user.'

    def add_arguments(self, parser):
        parser.add_argument('user_id', type=int, nargs='+',
                            help="""A list of user IDs for which to train a classifier."""
                            )
        parser.add_argument('--exhaustive', action='store_true',
                            help="""Try to look up missing abstracts from all registered 
            sources. Training will take significantly longer."""
                            )

    def handle(self, *args, **options):
        """The main entrypoint for this command."""

        for uid in options['user_id']:
            try:
                self.user = User.objects.get(pk=uid)
            except User.DoesNotExist as e:
                logger.error("Could not find user {}".format(uid))
                continue

            m = self._train(options['exhaustive'])

            if m is None:
                return

            # Save the trained classifier to the user
            self.user.classifier.classifier = m.classifier
            self.user.classifier.vectorizer = m.vectorizer
            self.user.classifier.save()

            logger.info('Finished training for user {}'.format(self.user.pk))

    def _get_random_articles(self, nr_samples, excluded_keys=[]):
        """Returns a list of randomly picked articles.

        Args:
            excluded_keys (list): Optional list of article IDs 
                that should not be picked.
        """
        # Get a list of keys that actually exist in the db
        valid_keys = Article.objects.values_list('pk', flat=True)

        # Remove the excluded keys from the valid list
        valid_keys = [x for x in valid_keys if x not in excluded_keys]

        # Randomly pick some valid keys
        random_keys = random.sample(valid_keys, nr_samples)

        # Get the corresponding articles
        articles = Article.objects.filter(pk__in=random_keys)
        return articles

    def _get_liked_articles(self):
        return Article.objects.filter(
            recommendation__user=self.user,
            recommendation__liked=True,
            recommendation__disliked=False
        )

    def _get_disliked_articles(self):
        return Article.objects.filter(
            recommendation__user=self.user,
            recommendation__liked=False,
            recommendation__disliked=True
        )

    def _get_clicked_articles(self):
        return Article.objects.filter(
            recommendation__user=self.user,
            recommendation__clicked=True,
            recommendation__liked=False,
            recommendation__disliked=False
        )

    def _get_uploaded_articles(self, exhaustive=False):
        uploads = UserUpload.objects.filter(user=self.user)
        all_articles = []
        for u in uploads:
            try:
                # Try to get all articles specified in this file
                articles_in_file = self._parse_file(u)
            except:
                logger.error("Error while parsing file:", exc_info=True)
                continue

            # Are we allowed to search for missing fields?
            if exhaustive:
                fetcher = Fetcher()
                for i, a in enumerate(articles_in_file):

                    # Skip article if it's already complete
                    if a.title and a.abstract and a.journal and a.authors_list:
                        continue

                    # We need at least a title to work with it
                    if not a.title:
                        continue

                    logger.info("Updating article {}/{} ...".format(i, len(articles_in_file)))

                    # Start a search in all sources for this specific title
                    queried_articles = fetcher.query_title(
                        a.title,
                        max_results=10
                    )

                    # The search probably returned more than one article
                    # Therefore loop over all those results
                    for aa in queried_articles:

                        # Find the first where the title matches perfectly
                        if self._titles_match(a, aa):
                            articles_in_file[i] = aa
                            break

            all_articles += articles_in_file
        return all_articles

    def _get_input_articles(self, exhaustive=False):
        pmid_list = UserTextInput.objects.filter(user=self.user)
        all_articles = []
        if pmid_list.count() > 0:
            pmid_list = pmid_list[0]
            pmids_text = pmid_list.pmid_list.strip()
            query_pmids = re.split(',', pmids_text)
            try:
                pmid_array = np.asarray(query_pmids, dtype=int)
            except:
                logger.error("PMIDs are not in correct format in the txt file.")
                return []
            fetcher = Fetcher()
            all_articles = fetcher.query_pmid(query_pmids, max_results=10000)
        return all_articles

    def _titles_match(self, x, y):
        """Compares the titles of Articles x and y. Ignores case of 
        characters as well as all non-alphanumeric characters.
        """
        pattern = re.compile('[\W_]+')
        x_title = pattern.sub('', x.title.lower())
        y_title = pattern.sub('', y.title.lower())
        return x_title == y_title

    def _add_articles_to_trainer(self, trainer, articles, target, weight=None):
        for a in articles:
            trainer.add_data(prepare_article(a), target, weight)

    def _train(self, exhaustive):
        logger.info('Training classifier for user {} ...'.format(self.user.pk))
        trainer = Trainer()

        # Get all articles the user interacted with
        likes = self._get_liked_articles()
        logger.info('  {} likes'.format(len(likes)))
        dislikes = self._get_disliked_articles()
        logger.info('  {} dislikes'.format(len(dislikes)))
        clicks = self._get_clicked_articles()
        logger.info('  {} clicks'.format(len(clicks)))
        uploaded = self._get_uploaded_articles(exhaustive)
        logger.info('  {} uploaded articles'.format(len(uploaded)))
        typed = self._get_input_articles(exhaustive)
        logger.info('  {} input articles'.format(len(typed)))

        # Ensure we have enough data to train with
        if len(likes) + len(dislikes) + len(clicks) + len(uploaded) + len(typed) < 10:
            logger.warning('ABORTING TRAINING. Not enough data for training.')
            return None

        # Configure trainer with our data
        self._add_articles_to_trainer(trainer, likes, Targets.INTERESTING)
        self._add_articles_to_trainer(trainer, dislikes, Targets.IRRELEVANT)
        self._add_articles_to_trainer(trainer, clicks, Targets.INTERESTING, 0.5)
        self._add_articles_to_trainer(trainer, uploaded, Targets.INTERESTING)
        self._add_articles_to_trainer(trainer, typed, Targets.INTERESTING)

        # Add random negative samples until we have the same amount as positives
        nr_positives = len(likes) + len(clicks) + len(uploaded) + len(typed)
        nr_negatives = len(dislikes)
        nr_padding_negatives = nr_positives - nr_negatives

        # Do we need to add random articles?
        if (nr_padding_negatives > 0):
            # Get a list of IDs of articles that were already considered for
            # training (Ignore uploaded files here, since their articles have
            # no ID in our database)
            article_list = list(itertools.chain(likes, dislikes, clicks, typed))
            excluded_keys = [a.pk for a in article_list]

            # Get a random set of articles and add them to the trainer. 
            # Avoid randomly picking a previously added article.
            logger.info('  {} random articles as negatives'.format(nr_padding_negatives))
            random_articles = self._get_random_articles(nr_padding_negatives, excluded_keys)
            self._add_articles_to_trainer(trainer, random_articles, Targets.IRRELEVANT)

        # Train the classifier 
        return trainer.train()

    def _parse_file(self, upload):
        # Get the absolute path to the file
        full_path = os.path.join(settings.BASE_DIR, settings.MEDIA_ROOT, upload.file.name)

        # Match filetype to parsing method
        with open(full_path, 'r', encoding="utf-8", errors="ignore") as file:
            if full_path.endswith('.bib'):
                return self._parse_bibtex(file)
            elif full_path.endswith('.ris'):
                return self._parse_ris(file)
            elif full_path.endswith('.xml'):
                return self._parse_endnote_xml(file)
            elif full_path.endswith('.txt'):
                return self._parse_txt(file)
        return []

    def _parse_txt(self, file):
        pmids_text = file.read().strip()
        pmid_list = re.split('\n|,| |;|, |; ', pmids_text)
        if len(pmid_list)>10000:
            pmid_list=pmid_list[:10000]
        pmid_clean_list = [pmid for pmid in pmid_list if pmid.isdigit()]
        fetcher = Fetcher()
        queried_articles = fetcher.query_pmid(pmid_clean_list, max_results=10000)
        return queried_articles

    def _parse_bibtex(self, file):
        """Parses a BibText file (.bib).
        Returns a list of articles found in the given file."""
        parser = bibtexparser.bparser.BibTexParser(
            common_strings=True,
            interpolate_strings=False,
            ignore_nonstandard_types=True,
        )
        bib_database = parser.parse_file(file, partial=True)

        articles = []
        for entry in bib_database.entries:
            a = Article()

            # Remove curly braces from all fields
            # This creates a "plain_" version for all fields
            entry = bibtexparser.customization.add_plaintext_fields(entry)

            if 'plain_title' in entry:
                # Remove line breaks from titles
                a.title = entry['plain_title'].replace('\n', '')
            if 'plain_abstract' in entry:
                a.abstract = entry['plain_abstract']
            if 'plain_journal' in entry:
                a.journal = entry['plain_journal']

            if 'author' in entry:
                a.authors_list = entry['author'].split(' and ')
            elif 'authors' in entry and isinstance(entry['authors'], list):
                a.authors_list = entry['authors']
            elif 'first_authors' in entry and isinstance(entry['first_authors'], list):
                a.authors_list = entry['first_authors']

            articles.append(a)
        return articles

    def _parse_ris(self, file):
        """Parses a RIS file (.ris).
        Returns a list of articles found in the given file."""
        articles = []
        entries = RISparser.readris(file)
        for entry in entries:
            a = Article()
            if 'title' in entry:
                a.title = entry['title']
            if 'abstract' in entry:
                a.abstract = entry['abstract']
            if 'journal' in entry:
                a.journal = entry['journal']

            if 'author' in entry:
                a.authors_list = entry['author'].split(' and ')
            elif 'authors' in entry and isinstance(entry['authors'], list):
                a.authors_list = entry['authors']
            elif 'first_authors' in entry and isinstance(entry['first_authors'], list):
                a.authors_list = entry['first_authors']

            articles.append(a)
        return articles

    def _parse_endnote_xml(self, file):
        """Parses an XML file with EndNote format.
        Returns a list of articles found in the given file"""

        # Helper method
        def find_tag(node, tags):
            """Checks every tag inside the `tags` list.
            Returns the first one that is not None.
            Returns None if no tag is found."""
            for tag in tags:
                e = node.find(tag)
                if e: break
            return e

        # Helper method
        def get_text(node):
            """Returns the node's text or the text inside a `style` tag.
            Returns an empty string if the given node is None."""
            if not node:
                return ""
            else:
                return node.text.strip() or node.find('style').text.strip()

        # Fill this list with Article objects
        articles = []

        # The XML might have varying syntax across files. Some might store the
        # title in <title></title> others in <titles><title></title></titles>.
        # Also the string might be wrapped in another <style> tag. We
        # have to accomodate for all that.

        root = ET.fromstring(file.read())
        records = root.findall('records/record')
        for record in records:
            a = Article()
            a.title = get_text(find_tag(
                record, ['title', 'titles/title', 'titles/full-title'])
            )

            a.journal = get_text(find_tag(
                record, ['periodical/title', 'periodical/full-title'])
            )

            a.abstract = get_text(find_tag(
                record, ['abstract'])
            )

            authors = []
            author_nodes = record.findall('contributors/authors/author')
            for author in author_nodes:
                name = get_text(author)
                authors.append(name)
            a.authors_list = authors

        return articles
