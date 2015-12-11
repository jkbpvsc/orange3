from itertools import chain
import numpy as np
from PyQt4.QtGui import QLayout
from PyQt4.QtCore import Qt

from Orange.data import Table, Domain, ContinuousVariable, StringVariable
from Orange.regression.linear import (
    LassoRegressionLearner, LinearModel, LinearRegressionLearner,
    RidgeRegressionLearner)
from Orange.preprocess import RemoveNaNClasses
from Orange.widgets import widget, settings, gui
from Orange.widgets.utils.owlearnerwidget import OWProvidesLearner
from Orange.widgets.utils.sql import check_sql_input


class OWLinearRegression(OWProvidesLearner, widget.OWWidget):
    name = "Linear Regression"
    description = "A linear regression algorithm with optional L1 and L2 " \
                  "regularization."
    icon = "icons/LinearRegression.svg"

    LEARNER = LinearRegressionLearner

    inputs = [("Data", Table, "set_data")] + OWProvidesLearner.inputs
    outputs = [("Linear Regression", LEARNER),
               ("Model", LinearModel),
               ("Coefficients", Table)]

    #: Types
    OLS, Ridge, Lasso = 0, 1, 2

    learner_name = settings.Setting("Linear Regression")
    ridge = settings.Setting(False)
    reg_type = settings.Setting(OLS)
    alpha_index = settings.Setting(0)
    autosend = settings.Setting(True)

    want_main_area = False

    alphas = list(chain([x / 10000 for x in range(1, 10)],
                        [x / 1000 for x in range(1, 20)],
                        [x / 100 for x in range(2, 20)],
                        [x / 10 for x in range(2, 9)],
                        range(1, 20),
                        range(20, 100, 5),
                        range(100, 1001, 100)))

    def __init__(self):
        super().__init__()

        self.data = None
        self.preprocessors = None

        box = gui.widgetBox(self.controlArea, "Learner/Predictor Name")
        gui.lineEdit(box, self, "learner_name")

        box = gui.widgetBox(self.controlArea, "Regularization")
        box = gui.radioButtons(
            box, self, "reg_type",
            btnLabels=["No regularization", "Ridge regression",
                       "Lasso regression"],
            callback=self._reg_type_changed)

        gui.separator(box)
        self.alpha_box = box2 = gui.widgetBox(box, margin=0)
        gui.widgetLabel(box2, "Regularization strength")
        self.alpha_slider = gui.hSlider(
            box2, self, "alpha_index",
            minValue=0, maxValue=len(self.alphas) - 1,
            callback=self._alpha_changed, createLabel=False)
        box3 = gui.widgetBox(box, orientation="horizontal")
        box3.layout().setAlignment(Qt.AlignCenter)
        self.alpha_label = gui.widgetLabel(box3, "")
        self._set_alpha_label()

        gui.auto_commit(self.controlArea, self, "autosend", "Apply",
                        checkbox_label="Apply on every change")

        self.layout().setSizeConstraint(QLayout.SetFixedSize)
        self.alpha_slider.setEnabled(self.reg_type != self.OLS)
        self.commit()

    @check_sql_input
    def set_data(self, data):
        self.data = data

    def handleNewSignals(self):
        self.commit()

    def _reg_type_changed(self):
        self.alpha_slider.setEnabled(self.reg_type != self.OLS)
        self.commit()

    def _set_alpha_label(self):
        self.alpha_label.setText(
            "Alpha: {}".format(self.alphas[self.alpha_index]))

    def _alpha_changed(self):
        self._set_alpha_label()
        self.commit()

    def apply(self):
        return self.commit()

    def commit(self):
        alpha = self.alphas[self.alpha_index]
        preprocessors = self.preprocessors
        if self.data is not None and np.isnan(self.data.Y).any():
            self.warning(0, "Missing values of target variable(s)")
            if not self.preprocessors:
                if self.reg_type == OWLinearRegression.OLS:
                    preprocessors = LinearRegressionLearner.preprocessors
                elif self.reg_type == OWLinearRegression.Ridge:
                    preprocessors = RidgeRegressionLearner.preprocessors
                else:
                    preprocessors = LassoRegressionLearner.preprocessors
            else:
                preprocessors = list(self.preprocessors)
            preprocessors.append(RemoveNaNClasses())
        args = {"preprocessors": preprocessors}
        if self.reg_type == OWLinearRegression.OLS:
            learner = LinearRegressionLearner(**args)
        elif self.reg_type == OWLinearRegression.Ridge:
            learner = RidgeRegressionLearner(alpha=alpha, **args)
        elif self.reg_type == OWLinearRegression.Lasso:
            learner = LassoRegressionLearner(alpha=alpha, **args)

        learner.name = self.learner_name
        predictor = None
        coef_table = None

        self.error(0)
        if self.data is not None:
            if not learner.check_learner_adequacy(self.data.domain):
                self.error(0, learner.learner_adequacy_err_msg)
            else:
                predictor = learner(self.data)
                predictor.name = self.learner_name
                domain = Domain(
                    [ContinuousVariable("coef", number_of_decimals=7)],
                    metas=[StringVariable("name")])
                coefs = [predictor.intercept] + list(predictor.coefficients)
                names = ["intercept"] + \
                    [attr.name for attr in predictor.domain.attributes]
                coef_table = Table(domain, list(zip(coefs, names)))
                coef_table.name = "coefficients"

        self.send("Linear Regression", learner)
        self.send("Model", predictor)
        self.send("Coefficients", coef_table)


if __name__ == "__main__":
    import sys
    from PyQt4.QtGui import QApplication

    a = QApplication(sys.argv)
    ow = OWLinearRegression()
    d = Table('iris')
    ow.set_data(d)
    ow.show()
    a.exec_()
    ow.saveSettings()
