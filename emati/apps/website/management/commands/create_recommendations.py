import sklearn
import datetime

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from machinelearning.ranker import ArticleRanker
from machinelearning.utils import Targets
from website.models import Article, Classifier, Recommendation

from machinelearning.utils import Targets, prepare_article, get_path_Bert_classifier,Bert_Pretrained
from transformers import BertTokenizer, BertForSequenceClassification
# from transformers import Trainer
# import torch
# import torch.nn.functional as F
# from django.conf import settings
# import os

import logging
logger = logging.getLogger(__name__)



class Command(BaseCommand):
    help = 'Calculate scores for recommendations for given users and articles.'

    # Predictions are calculated in batches
    BATCH_SIZE = 10000
    BATCH_SIZE_BERT = 64
    # Create recommendations only for the best scores
    RECOMMENDATIONS_PER_BATCH = 100
    MAX_BERT_RECOMMENDATIONS_PER_BATCH = 4

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

    def add_articles_for_Bert(self, articles):
        """Adds a list of articles as data samples for later ranking."""
        data = []
        for a in articles:
            sample = prepare_article(a)
            data.append(sample)
        return data

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

            if u.profile.default_classifier:
                if not u.classifier.is_initialized():
                    logger.warning("Skipping user. Classifier not yet initialized.")
                    continue
                # Create a ranker using this user's classifier
                ranker = ArticleRanker(u.classifier, default_classifier=u.profile.default_classifier)

                # Calculate scores and create recommendations
                self._rank_articles(u, ranker, articles)
            else:
                if not u.bert_classifier.is_initialized():
                    logger.warning("Skipping user. Classifier not yet initialized.")
                    continue
                self._rank_articles_with_Bert(u, articles)
        
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

    def _rank_articles_with_Bert(self, u, articles):
        start = 0
        end = start + self.BATCH_SIZE_BERT
        num_articles = articles.count()
        batch_nr = 1
        model_name = Bert_Pretrained.MODEL_NAME
        tokenizer = BertTokenizer.from_pretrained(model_name)
        # Load trained model
        path = get_path_Bert_classifier(u.pk)
        try:
            model = BertForSequenceClassification.from_pretrained(path, num_labels=2)
        except sklearn.exceptions.NotFittedError:
            logger.exception("Can't run the classifier, no model was supplied.", exc_info=True)
            return

        # Classify in batches
        while start < num_articles:
            logger.info("  batch {} ({}/{}):".format(
                batch_nr,
                min(end, num_articles),
                num_articles)
            )

            # Prepare this batch
            logger.info("  loading data ...")
            article_batch = articles[start:end]
            X_test = self.add_articles_for_Bert(article_batch)

            X_test_tokenized = tokenizer(X_test, padding=True, truncation=True, max_length=300, return_tensors="pt")

            # test_trainer = Trainer(model)
            # raw_pred, _, _ = test_trainer.predict(test_dataset)

            logger.info("  calculating scores ...")
            outputs = model(**X_test_tokenized)
            # get output probabilities by doing softmax
            probs = outputs[0].softmax(1)

            scores = [p[Targets.INTERESTING].item() for p in probs]
            high_score_recommendations = len([x for x in scores if x >= 0.6])
            articles_with_scores = zip(article_batch, scores)
            articles_with_scores = sorted(
                articles_with_scores,
                key=lambda x: x[1],
                reverse=True
            )

            recommendations_per_batch = high_score_recommendations
            if self.MAX_BERT_RECOMMENDATIONS_PER_BATCH < high_score_recommendations:
                recommendations_per_batch = self.MAX_BERT_RECOMMENDATIONS_PER_BATCH

            best_articles = articles_with_scores[:recommendations_per_batch]

            # Create recommendations with these scores
            logger.info("  creating recommendations ...")
            for (i, (article, score)) in enumerate(best_articles):
                # Create a new or overwrite an existing recommendation
                r, _ = Recommendation.objects.get_or_create(
                    user=u,
                    article=article
                )
                r.score = score
                r.save()

            start += self.BATCH_SIZE_BERT
            end = start + self.BATCH_SIZE_BERT
            batch_nr += 1

