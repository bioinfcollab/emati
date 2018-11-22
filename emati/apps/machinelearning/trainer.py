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
from sklearn.model_selection import cross_val_score
from sklearn.externals import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB

import logging
logger = logging.getLogger(__name__)

from . import utils


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