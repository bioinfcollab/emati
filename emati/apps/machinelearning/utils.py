from sklearn.externals import joblib
import os
from django.conf import settings

import torch
import transformers
import logging
logger = logging.getLogger(__name__)

def save_model(model, filename):
    """Serializes a model and writes it to disk."""
    joblib.dump(model, filename)


def load_model(filename):
    """Loads a model from a file. Returns the model."""
    return joblib.load(filename)

def get_path_Bert_classifier(user_id):
    """Returns the absolute path for a given file when it belongs
    to this classifier."""
    return os.path.join(
        settings.BASE_DIR,
        settings.MEDIA_ROOT,
        'bert_classifiers/user_{}/'.format(user_id),

    )
class Bert_Pretrained():
    MODEL_NAME = "bert-base-uncased"

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

#Create torch dataset
class Dataset(torch.utils.data.Dataset):
    def __init__(self, encodings, labels=None):
        self.encodings = encodings
        self.labels = labels

    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        if self.labels:
            item["labels"] = torch.tensor(self.labels[idx])
        return item

    def __len__(self):
        return len(self.encodings["input_ids"])

class LoggerLogCallback(transformers.TrainerCallback):
    def on_log(self, args, state, control, logs=None, **kwargs):
        control.should_log = False
        _ = logs.pop("total_flos", None)
        if state.is_local_process_zero:
            logger.info(logs)  # using your custom logger
