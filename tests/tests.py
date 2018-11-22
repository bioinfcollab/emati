import os
from datetime import date, datetime, timedelta

from django.test import TestCase
from django.db.utils import IntegrityError
from django.db.models import Q
from django.contrib.auth.models import User
from django.core.management import call_command
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

import machinelearning as ml
from machinelearning.trainer import Trainer
from machinelearning.ranker import Ranker
from website.models import Article, Recommendation, Classifier, UserUpload
from fetching import Fetcher

import logging
logging.disable(logging.CRITICAL)


class FetcherTest(TestCase):

    def test_fetching(self):
        nr_articles = Article.objects.all().count()
        self.assertEqual(nr_articles, 0)
        call_command('fetch_papers', '--last-day')
        nr_articles = Article.objects.all().count()
        self.assertGreater(nr_articles, 0)


class ClassifierTest(TestCase):

    def setUp(self):
        self.u = User.objects.create(username='testuser', email='user@mail.com')

    def test_delete_classifier_with_user(self):
        u = User.objects.create(username='newuser', email='new@user.com')
        u.classifier.classifier = "FOO"
        u.classifier.vectorizer = "BAR"
        u.classifier.save()
        path_clf = u.classifier.path_clf
        path_vec = u.classifier.path_vec
        self.assertTrue(os.path.exists(path_clf))
        self.assertTrue(os.path.exists(path_vec))
        u.delete()
        self.assertFalse(os.path.exists(path_clf))
        self.assertFalse(os.path.exists(path_vec))

    def test_overwrite_classifier(self):
        """There should be a way to overwrite a user's classifier."""
        u = User.objects.all()[0]
        u.classifier.vectorizer = None
        u.classifier.save()

    def test_multiple_classifier_creation(self):
        """A user should only have exactly one classifier."""
        u = User.objects.create(username='newuser', email='new@user.com')
        foo = u.classifier # Force classifier creation by accessing it
        with self.assertRaises(IntegrityError):
            Classifier.objects.create(user=u)
    
    def test_saving_empty_classifier(self):
        """Creating a classifier without a user should be impossible."""
        c = Classifier()
        self.assertRaises(IntegrityError, c.save)

    def test_create_classifier(self):
        """Manually creating a classifier."""
        u = User.objects.all()[0]
        c = Classifier.objects.create(user=u)

    def test_automatic_classifier_creation(self):
        """Classifiers should be automatically created when first accessed."""
        u = User.objects.create(username='newuser', email='new@user.com')
        u.classifier


class NewsletterTest(TestCase):

    def test_send_newsletter(self):
        pass
        

class TrainerTest(TestCase):

    def test_training(self):
        u = User.objects.create(username='testuser', email='test@user.com')
        trainer = Trainer()
        for i in range(10):
            trainer.add_data("This is a very interesting and relevant and important.", ml.Targets.INTERESTING)
            trainer.add_data("This is totally boring and irrelevant. Do not read it.", ml.Targets.IRRELEVANT)
        model = trainer.train()
        self.assertIsNotNone(model)
        self.assertIsNotNone(model.classifier)
        self.assertIsNotNone(model.vectorizer)
        ranker = Ranker(model)
        score_tuple = ranker.predict_single("very interesting, important, relevant")
        self.assertGreater(score_tuple[ml.Targets.INTERESTING], score_tuple[ml.Targets.IRRELEVANT])
        score_tuple = ranker.predict_single("very boring and irrelevant")
        self.assertGreater(score_tuple[ml.Targets.IRRELEVANT], score_tuple[ml.Targets.INTERESTING])


    def test_training_without_samples(self):
        """Training shouldn't be successful if no data is provided."""
        u = User.objects.create(username='testuser', email='test@user.com')
        trainer = Trainer()
        model = trainer.train()
        self.assertIsNone(model)


class UserTest(TestCase):

    def _create_user(self, username, password):
        u = User.objects.create_user(
            username=username, 
            email='{}@test.com'.format(username), 
            password=password
        )
        u.profile.terms_consent = True
        u.profile.save()
        return u

    def test_reset_account(self):
        u = self._create_user('TestUser', 'test')
        self.client.login(username='TestUser', password='test')

        # Create a dummy article and a respective recommendation
        a = Article.objects.create(
            title='my title', 
            abstract='my abstract',
            pubdate=date.today()-timedelta(days=1),        
        )
        r = Recommendation.objects.create(
            user=u,
            article=a,
            score=0,
            clicked=False,
            liked=False,
            disliked=False
        )

        self.client.post(reverse('log_click', args=[a.pk]))
        r.refresh_from_db()
        self.assertTrue(r.clicked)

        self.client.post(reverse('log_like', args=[a.pk]))
        r.refresh_from_db()
        self.assertTrue(r.liked)

        self.client.post(reverse('log_dislike', args=[a.pk]))
        r.refresh_from_db()
        self.assertTrue(r.disliked)
        self.assertFalse(r.liked)

        self.client.post(reverse('log_like', args=[a.pk]))
        r.refresh_from_db()
        self.assertTrue(r.liked)
        self.assertFalse(r.disliked)

        # Upload some files
        bib_file = SimpleUploadedFile("file.bib", b"file_content", content_type="text/html")
        self.client.post(reverse('settings'), {'newfile': bib_file})
        self.assertEqual(UserUpload.objects.filter(user=u).count(), 1)

        # Create a dummy classifier
        u.classifier.classifier = "FOO"
        u.classifier.vectorizer = "BAR"
        u.classifier.save()
        self.assertTrue(u.classifier.is_initialized())

        # Reset account
        self.client.post(reverse('account_reset'))

        # Assert everything is reset
        u.refresh_from_db()
        self.assertFalse(u.classifier.is_initialized())
        self.assertQuerysetEqual(UserUpload.objects.filter(user=u), [])
        self.assertQuerysetEqual(
            Recommendation.objects
                .filter(user=u)
                .filter(Q(clicked=True) | Q(liked=True) | Q(disliked=True)
            ),
            []
        )


    def test_delete_account(self):
        u = self._create_user('TestUser', 'test')
        self.client.login(username='TestUser', password='test')
        response = self.client.post(reverse('account_delete'))
        self.assertQuerysetEqual(User.objects.all(), [])
    

class ArticleTest(TestCase):

    def test_avoid_duplicate_articles(self):
        a1 = Article(
            title='This is an article', 
            abstract='Here we talk about the great things we discovered', 
            journal='The Testing Journal', 
            authors_string='Tester,Peter;Checker,Bobby', 
            url_fulltext='https://do.not.click.me', 
            url_source='https://somewebsitewherewefoundthearticle.com', 
            pubdate=datetime.strptime('2018-06-24', '%Y-%m-%d').date()
        )
        a1.save()

        a2 = Article(
            title='This is an article', 
            abstract='Here we talk about the great things we discovered', 
            journal='The Testing Journal', 
            authors_string='Tester,Peter;Checker,Bobby', 
            url_fulltext='https://do.not.click.me', 
            url_source='https://somewebsitewherewefoundthearticle.com', 
            pubdate=datetime.strptime('2018-06-24', '%Y-%m-%d').date()
        )
        self.assertRaises(IntegrityError, a2.save)


class RecommendationTest(TestCase):

    def setUp(self):
        a = Article(
            title='This is an article', 
            abstract='Here we talk about the great things we discovered', 
            journal='The Testing Journal', 
            authors_string='Tester,Peter;Checker,Bobby', 
            url_fulltext='https://do.not.click.me', 
            url_source='https://somewebsitewherewefoundthearticle.com', 
            pubdate=date.today()
        )
        a.save()


    def test_avoid_duplicate_recommendations(self):
        u = User.objects.create(username='testuser', email='test@user.com')
        a = Article.objects.all()[0]

        r1 = Recommendation(
            user=u,
            article=a,
            score=0.7,
            clicked=False,
            liked=False,
            disliked=False
        )
        r1.save()

        r2 = Recommendation(
            user=u,
            article=a,
            score=0.9,
            clicked=True,
            liked=True,
            disliked=True
        )

        self.assertRaises(IntegrityError, r2.save)


    def test_create_recommendations(self):
        u = User.objects.create(username='testuser', email='test@user.com')
        trainer = Trainer()
        for i in range(10):
            trainer.add_data("This is a very interesting and relevant and important.", ml.Targets.INTERESTING)
            trainer.add_data("This is totally boring and irrelevant. Do not read it.", ml.Targets.IRRELEVANT)
        model = trainer.train()
        u.classifier.classifier = model.classifier
        u.classifier.vectorizer = model.vectorizer
        u.classifier.save()

        self.assertEqual(Recommendation.objects.all().count(), 0)
        call_command("create_recommendations", "--last-week")
        self.assertEqual(Recommendation.objects.all().count(), 1)
