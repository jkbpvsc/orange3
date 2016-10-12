# pylint: disable=missing-docstring

from Orange.data import Table
from Orange.classification import NaiveBayesLearner, TreeLearner
from Orange.evaluation.testing import CrossValidation
from Orange.widgets.evaluate.owconfusionmatrix import OWConfusionMatrix
from Orange.widgets.tests.base import WidgetTest


class TestOWConfusionMatrix(WidgetTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        bayes = NaiveBayesLearner()
        tree = TreeLearner()
        iris = Table("iris")
        titanic = Table("titanic")
        common = dict(k=3, store_data=True)
        cls.results_1_iris = CrossValidation(iris, [bayes], **common)
        cls.results_2_iris = CrossValidation(iris, [bayes, tree], **common)
        cls.results_2_titanic = CrossValidation(titanic, [bayes, tree],
                                                **common)

    def setUp(self):
        self.widget = self.create_widget(OWConfusionMatrix,
                                         stored_settings={"auto_apply": False})

    def test_selected_learner(self):
        """Check learner and model for various values of all parameters
        when pruning parameters are not checked
        """
        self.send_signal("Evaluation Results", self.results_2_iris)
        self.assertEqual(self.widget.selected_learner, [0])
        self.widget.selected_learner[:] = [1]
        self.send_signal("Evaluation Results", self.results_2_titanic)
        self.widget.selected_learner[:] = [1]
        self.send_signal("Evaluation Results", self.results_1_iris)
        self.widget.selected_learner[:] = [0]
        self.send_signal("Evaluation Results", None)
        self.send_signal("Evaluation Results", self.results_1_iris)
        self.widget.selected_learner[:] = [0]

    def test_outputs(self):
        self.send_signal("Evaluation Results", self.results_1_iris)

        # check selected data output
        self.assertIsNone(self.get_output("Selected Data"))

        # select data instances
        self.widget.select_correct()

        # check selected data output
        selected = self.get_output("Selected Data")
        self.assertGreater(len(selected), 0)

        # check output when data is removed
        self.send_signal("Evaluation Results", None)
        self.assertIsNone(self.get_output("Selected Data"))
