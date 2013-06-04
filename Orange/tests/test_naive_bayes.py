import unittest
import numpy as np

from Orange import data
import Orange.classification.naive_bayes as nb
from Orange.evaluation import scoring


class NaiveBayesTest(unittest.TestCase):
    def test_NaiveBayes(self):
        nrows = 1000
        ncols = 10
        x = np.random.random_integers(1, 3, (nrows, ncols))
        col = np.random.randint(ncols)
        y = x[:nrows, col].reshape(nrows, 1) + 100

        x1, x2 = np.split(x, 2)
        y1, y2 = np.split(y, 2)
        t = data.Table(x1, y1)
        learn = nb.BayesLearner()
        clf = learn(t)
        z = clf(x2)
        self.assertTrue((z.reshape((-1, 1)) == y2).all())

    def test_BayesStorage(self):
        nrows = 200
        ncols = 10
        x = np.random.random_integers(0, 5, (nrows, ncols))
        x[:, 0] = np.ones(nrows) * 3
        y = x[:, ncols / 2].reshape(nrows, 1)
        x1, x2 = np.split(x, 2)
        y1, y2 = np.split(y, 2)
        t1 = data.Table(x1, y1)
        t2 = data.Table(x2, y2)
        learn = nb.BayesStorageLearner()
        clf = learn(t1)
        z2 = clf(x2)
        ca = scoring.CA(t2, z2)
        self.assertGreater(ca, 0.5)
