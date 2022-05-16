#!/usr/bin/python

from .utils import Targets, prepare_article,Bert_Pretrained
from transformers import BertTokenizer, BertForSequenceClassification

class Ranker():
    """A general purpose ranker.
    Acts as an abstraction layer over the machine learning functions.
    """

    def __init__(self, model):
        self.model = model
        self.data = []

    
    def set_model(self, model):
        """Specify which model to use for prediction."""
        self.model = model


    def reset_data(self):
        """Resets previously given data samples."""
        self.data = []


    def add_data(self, data):
        """Feed a data sample for later class prediction."""
        self.data.append(data)
    

    def get_predictions(self):
        """Predict the class of a set of data samples.

        Make sure you called `set_model` and `add_data` before calculating the
        prediction.

        Returns: A list where each item is the probability for each respective
            data item. The probabilities are in the same order as the respective
            items were added using `add_data`. Each probability is a list itself
            with as many items as the number of classes the model was trained
            on. Each value represents the probability with which this data point
            belongs to the resepctive class. E.g.: [[0.3, 0.7], [...], ...]
            Means, the first sample belongs to class 0 with 30% and to class 1
            with 70%.
        """
        if not self.model:
            raise ValueError("Can't run the classifier, no model was supplied.")
        
        if not self.data:
            raise ValueError("Can't run the classifier, no data to predict.")

        x_tfidf = self.model.vectorizer.transform(self.data)
        prediction = self.model.classifier.predict_proba(x_tfidf)

        return prediction


    def predict_single(self, data):
        """Predict a single data sample.
        
        Args:
            data (string): The sample of which to predict the class.

        Returns:
            A list where each value represents the probability that the
            given sample belongs to this class.
            E.g.: [0.3, 0.4, 0.2, 0.2]
            Means, the sample belongs to class 0 with 30%, to class 1 with 40%
            and to classes 2 and 3 with 20% respectively.
        """
        self.reset_data()
        self.add_data(data)
        return self.get_predictions()[0]


    def get_bert_predictions(self):
        """Predict the class of a set of data samples.

        Make sure you called  `add_data` before calculating the
        prediction.

        Returns: A list where each item is the probability for each respective
            data item. The probabilities are in the same order as the respective
            items were added using `add_data`. Each probability is a list itself
            with as many items as the number of classes the model was trained
            on. Each value represents the probability with which this data point
            belongs to the resepctive class. E.g.: [[0.3, 0.7], [...], ...]
            Means, the first sample belongs to class 0 with 30% and to class 1
            with 70%.
        """
        if not self.model:
            raise ValueError("Can't run the classifier, no model was supplied.")

        if not self.data:
            raise ValueError("Can't run the classifier, no data to predict.")

        tokenizer = BertTokenizer.from_pretrained(Bert_Pretrained.MODEL_NAME)
        # Load trained model
        bert_model = BertForSequenceClassification.from_pretrained(self.model.path_clf, num_labels=2)
        data_tokenized = tokenizer(self.data, padding=True, truncation=True, max_length=300, return_tensors="pt")
        outputs = bert_model(**data_tokenized)
        # get output probabilities by doing softmax
        probs = outputs[0].softmax(1)
        return probs

class ArticleRanker(Ranker):
    """A ranker specifically designed to rank Articles.
    """
    def __init__(self, model, default_classifier):
        self.default_clf = default_classifier
        super().__init__(model)

    def add_article(self, article):
        """Adds a single article as data sample for later ranking."""
        sample = prepare_article(article)
        self.add_data(sample)

    
    def add_articles(self, articles):
        """Adds a list of articles as data samples for later ranking."""
        for a in articles:
            sample = prepare_article(a)
            self.add_data(sample)

    
    def rank_articles(self, articles):
        """Takes a list of articles, ranks them using the specified 
        classifier, and returns them sorted by their score.

        Returns a list of tuples where each tuple consists of (article,score).
        The list is sorted in descending order, the first item having the
        highest score.
        """
        self.add_articles(articles)
        if self.default_clf:
            predictions = self.get_predictions()
        else:
            predictions = self.get_bert_predictions()
        # Score is only the probability with which an article 
        # belongs to the "interesting"-class
        scores = [p[Targets.INTERESTING] for p in predictions]

        return sorted(zip(articles, scores), key=lambda x: x[1], reverse=True)
