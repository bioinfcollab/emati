import sklearn
import datetime

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from machinelearning.ranker import ArticleRanker
from machinelearning.utils import Targets
from website.models import Article, Classifier, Recommendation


import logging
logger = logging.getLogger(__name__)



class Command(BaseCommand):
    help = 'Calculate scores for recommendations for given users and articles.'

    # Predictions are calculated in batches
    BATCH_SIZE = 10000

    # Create recommendations only for the best scores
    RECOMMENDATIONS_PER_BATCH = 100


    def add_arguments(self, parser):
        parser.add_argument(
            '-u', '--user-ids', 
            type=int,
            nargs='+',
            help="Only consider the users in the given list of keys.")
        parser.add_argument(
            '-a', '--article-ids',
            type=int,
            nargs='+',
            help="""Restrict the set of articles that are considered for
            recommendations.""")
        parser.add_argument(
            '--last-week',
            action='store_true',
            help="Only consider articles published within the last seven days.")
        parser.add_argument(
            '--unranked-articles',
            action='store_true',
            help="""For each specified user, find all articles that don't 
            have a score yet and create recommendations for them.""")
        parser.add_argument(
            '--all-articles', 
            action='store_true', 
            help="""Consider every article in the database when creating recommendations. 
            Skips articles that already have a recommendation. WARNING: this 
            might take a long time depending on the number of articles in 
            the database.""")
        parser.add_argument(
            '--preserve-existing', 
            action='store_true',
            help="""Ensures that existing recommendations are skipped and not recalculated.""")


    def _get_user_list(self, **options):
        """Returns the list of users we are supposed to work on."""
        if options['user_ids']:
            return User.objects.filter(pk__in=options['user_ids'])
        else:
            return User.objects.all()
            

    def _get_article_list(self, user, **options):
        """Returns the list of articles we are supposed to classify."""
        # ... determine which articles to work on
        if options['all_articles']:
            return Article.objects.all()
        elif options['unranked_articles']:
            return Article.objects.exclude(recommendation__user=user.pk)
        elif options['last_week']:
            d = datetime.date.today() - datetime.timedelta(days=8)
            return Article.objects.filter(pubdate__gte=d)
        elif options['article_ids']:
            return Article.objects.filter(pk__in=options['article_ids'])
        else:
            return None


    def handle(self, *args, **options):
        """The main entry point for this command."""

        users = self._get_user_list(**options)
        if not users:
            self.stderr.write("No users to work with.")
            return
        
        for u in users:

            articles = self._get_article_list(user=u, **options)
            if not articles:
                logger.warning(
                    "Skipping user {}. No articles "
                    "found for classification.".format(u.pk)
                )
                continue

            logger.info("Creating recommendations for user {} ...".format(u.pk))

            if options['preserve_existing']:
                # Exclude all those that already have a score
                articles = articles.exclude(recommendation__user=u.pk)

            num_articles = articles.count()
            if num_articles <= 0:
                logger.info("  no articles found")
                continue

            logger.info("  {} articles to rank".format(articles.count()))

            if not u.classifier.is_initialized():
                logger.warning("Skipping user. Classifier not yet initialized.")
                continue
            
            # Create a ranker using this user's classifier
            ranker = ArticleRanker(u.classifier)

            # Calculate scores and create recommendations
            self._rank_articles(u, ranker, articles)
        
        logger.info("Finished creating recommendations")



    def _rank_articles(self, user_id, ranker, articles):

        start = 0
        end = start + self.BATCH_SIZE
        num_articles = articles.count()
        batch_nr = 1

        # Classify in batches
        while start < num_articles:
            logger.info("  batch {} ({}/{}):".format(
                batch_nr,
                min(end, num_articles), 
                num_articles)
            )

            # Prepare this batch
            article_batch = articles[start:end]
            ranker.reset_data()

            # Add those articles to the ranker
            logger.info("  loading data ...")
            ranker.add_articles(article_batch)
            
            # Calculate the predictions
            try:
                logger.info("  calculating scores ...")
                predictions = ranker.get_predictions()
            except sklearn.exceptions.NotFittedError:
                logger.exception("Error while calculating scores. The "
                    "classifier wasn't initialized yet. Retrain the "
                    "model and try again.", exc_info=True)
                return

            # Sort by scores
            scores = [p[Targets.INTERESTING] for p in predictions]
            articles_with_scores = zip(article_batch, scores)
            articles_with_scores = sorted(
                articles_with_scores, 
                key=lambda x: x[1], 
                reverse=True
            )

            # Only use the best articles
            best_articles = articles_with_scores[:self.RECOMMENDATIONS_PER_BATCH]

            # Create recommendations with these scores
            logger.info("  creating recommendations ...")
            for (i, (article, score)) in enumerate(best_articles):

                # Create a new or overwrite an existing recommendation
                r, _ = Recommendation.objects.get_or_create(
                    user=user_id, 
                    article=article
                )
                r.score = score
                r.save()
            
            start += self.BATCH_SIZE
            end = start + self.BATCH_SIZE
            batch_nr += 1
