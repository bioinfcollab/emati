#!/usr/bin/python

"""
Responsible for training a machine learning model.

Example:
    import machinelearning as ml
    from machinelearning.trainer import Trainer
    trainer = Trainer()
    trainer.add_data("this is very interesting to the user", Targets.INTERESTING)
    trainer.add_data("this is a totally irrelevant article", Targets.IRRLEVANT)
    my_model = trainer.train()
    ml.utils.save_model(my_model, 'my_model')    
"""

import os
import numpy as np
from sklearn.model_selection import cross_val_score,train_test_split
from sklearn.externals import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB

import logging

from .utils import LoggerLogCallback

logger = logging.getLogger(__name__)

from . import utils

import torch
import transformers
from transformers.file_utils import is_tf_available, is_torch_available
from transformers import BertForSequenceClassification, BertTokenizer
from transformers import Trainer, TrainingArguments
import random
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score


class Sample:
    """A training sample used for training a model.
    
    In our case this represents an article.

    Args:
        data (string): The data we will be learning from. In case of articles
            this is simply the abstract and the title.
        target (int): The target class that this sample belongs to. See class
            `Targets` for a list of supported classes.
        weight (float): The weight of this sample. Defaults to 1.
    """

    def __init__(self, data, target, weight=1):
        self.data = data
        self.target = target
        self.weight = weight


class Trainer:
    """Responsible for training machine learning models."""

    def __init__(self):
        self.model = utils.Model()
        self.samples = []

        # Amount of cross-validation
        self.cv = 10
    

    def add_data(self, data, target, weight=None):
        """Adds one sample to the training set.

        Args:
            data (string): Value that is used to learn/predict the target class.
            target (int): The class this sample belongs to. Use one of the `Targets` enums.
        """
        if weight:
            sample = Sample(data, target, weight)
        else:
            sample = Sample(data, target)
        self.samples.append(sample)


    def train(self):
        """Starts training a model on the supplied data samples.
        
        Returns:
            A trained classifier.
        """
        # Without data we can't do anything
        if not self.samples:
            return None

        data = []
        targets = []
        weights = []
        for s in self.samples:
            data.append(s.data)
            targets.append(s.target)
            weights.append(s.weight)

        logger.info("Extracting features ...")
        self.model.vectorizer = TfidfVectorizer()

        # Convert to numpy arrays
        data_np = np.array(data)
        targets_np = np.array(targets)
        weights_np = np.array(weights)

        x_train_tfidf = self.model.vectorizer.fit_transform(data_np)
        logger.info("  {} samples".format(len(self.samples)))
        logger.info("  {} features".format(x_train_tfidf.shape[1]))

        logger.info("Training the model ...")
        self.model.classifier = MultinomialNB()
        self.model.classifier.fit(x_train_tfidf, targets_np, weights_np)

        logger.info("Calculating cross-validation ...")
        precision = cross_val_score(self.model.classifier, x_train_tfidf, targets_np, cv=self.cv, scoring='precision')
        recall = cross_val_score(self.model.classifier, x_train_tfidf, targets_np, cv=self.cv, scoring='recall')
        p = precision.mean()
        r = recall.mean()
        logger.info("  Precision:\t{:.2f} (+/- {:.2f})".format(p, precision.std() * 2))
        logger.info("  Recall:\t{:.2f} (+/- {:.2f})".format(r, recall.std() * 2))
        logger.info("  F-Measure:\t{:.2f}".format(2 * p * r / (p + r)))

        return self.model

    def train_BERT(self, user_id):
        #set_seed(1)
        if not self.samples:
            return None
        data = []
        targets = []
        for s in self.samples:
            data.append(s.data)
            targets.append(s.target)
        # text_length = [len(a.split(' ')) for a in data]
        # print("mean text length is "+ str(statistics.mean(text_length)))
        # print("median text length is " + str(statistics.median(text_length)))
        model_name = utils.Bert_Pretrained.MODEL_NAME
        tokenizer = BertTokenizer.from_pretrained(model_name)
        mdl = BertForSequenceClassification.from_pretrained(model_name, num_labels=2)
        test_size = 0.2
        (train_texts, valid_texts, train_labels, valid_labels) = train_test_split(data, targets,
                                                                                  test_size=test_size)
        X_train_tokenized = tokenizer(train_texts, padding=True, truncation=True, max_length=300)
        X_val_tokenized = tokenizer(valid_texts, padding=True, truncation=True, max_length=300)

        train_dataset = utils.Dataset(X_train_tokenized, train_labels)
        val_dataset = utils.Dataset(X_val_tokenized, valid_labels)
        save_path = utils.get_path_Bert_classifier(user_id)
        self.create_path(save_path)

        args = TrainingArguments(
            output_dir=save_path,
            evaluation_strategy="epoch",
            save_strategy="epoch",
            per_device_train_batch_size=32,
            per_device_eval_batch_size=64,
            # per_device_train_batch_size=8,
            # per_device_eval_batch_size=8,
            num_train_epochs=3,
            seed=0,
            load_best_model_at_end=True,
            save_total_limit=1,
            logging_strategy="epoch",
            logging_dir=save_path + 'logs',

        )
        trnr = transformers.Trainer(
            model=mdl,
            args=args,
            train_dataset=train_dataset,
            eval_dataset=val_dataset,
            compute_metrics=compute_metrics,
            callbacks=[utils.LoggerLogCallback]
        )
        # Train pre-trained model
        trnr.train()
        trnr.save_model()
        return save_path

    def create_path(self, path):
        """Creates necessary directories in a path if they don't exist."""
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))

def compute_metrics(p):
    pred, labels = p
    pred = np.argmax(pred, axis=1)

    accuracy = accuracy_score(y_true=labels, y_pred=pred)
    recall = recall_score(y_true=labels, y_pred=pred)
    precision = precision_score(y_true=labels, y_pred=pred)
    f1 = f1_score(y_true=labels, y_pred=pred)

    return {"accuracy": accuracy, "precision": precision, "recall": recall, "f1": f1}

def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    if is_torch_available():
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        # ^^ safe to call this function even if cuda is not available
    if is_tf_available():
        import tensorflow as tf

        tf.random.set_seed(seed)

