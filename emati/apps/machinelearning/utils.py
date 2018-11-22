from sklearn.externals import joblib
import os


def save_model(model, filename):
    """Serializes a model and writes it to disk."""
    joblib.dump(model, filename)


def load_model(filename):
    """Loads a model from a file. Returns the model."""
    return joblib.load(filename)


class Targets():
    """The target classes we want to predict"""
    INTERESTING = 0
    IRRELEVANT = 1


class Model():
    """A machine learning model. Consist of a vectorizer and a classifier.

    Use `save_model()` and `load_model()` for serialization.
    """
    def __init__(self):
        self.vectorizer = None
        self.classifier = None


def prepare_article(article):
    """Returns an article represented as a single string.

    Use this to specify which fields of an article are accessible to the
    machine learning. Expects the given `article` object to be an instance
    of website.models.Article.
    """
    return ' '.join([
            article.title,
            article.abstract,
            article.journal,
            article.authors_string
        ])