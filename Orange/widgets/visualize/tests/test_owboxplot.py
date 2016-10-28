# Test methods with long descriptive names can omit docstrings
# pylint: disable=missing-docstring
from unittest import skip

import numpy as np
from Orange.data import Table, ContinuousVariable
from Orange.widgets.visualize.owboxplot import OWBoxPlot
from Orange.widgets.tests.base import WidgetTest


class OWBoxPlotTests(WidgetTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.iris = Table("iris")
        cls.zoo = Table("zoo")
        cls.housing = Table("housing")
        cls.titanic = Table("titanic")
        cls.heart = Table("heart_disease")

    def setUp(self):
        self.widget = self.create_widget(OWBoxPlot)

    def test_input_data(self):
        """Check widget's data"""
        self.send_signal("Data", self.iris)
        self.assertEqual(len(self.widget.attrs), 5)
        self.assertEqual(len(self.widget.group_vars), 2)
        self.assertFalse(self.widget.display_box.isHidden())
        self.assertTrue(self.widget.stretching_box.isHidden())
        self.send_signal("Data", None)
        self.assertEqual(len(self.widget.attrs), 0)
        self.assertEqual(len(self.widget.group_vars), 0)
        self.assertTrue(self.widget.display_box.isHidden())
        self.assertFalse(self.widget.stretching_box.isHidden())

    def test_input_data_missings_cont_group_var(self):
        """Check widget with continuous data with missing values and group variable"""
        data = self.iris
        data.X[:, 0] = np.nan
        self.send_signal("Data", data)
        # used to crash, see #1568

    def test_input_data_missings_cont_no_group_var(self):
        """Check widget with continuous data with missing values and no group variable"""
        data = self.housing
        data.X[:, 0] = np.nan
        self.send_signal("Data", data)
        # used to crash, see #1568

    def test_input_data_missings_disc_group_var(self):
        """Check widget with discrete data with missing values and group variable"""
        data = self.zoo
        data.X[:, 0] = np.nan
        self.send_signal("Data", data)

    def test_input_data_missings_disc_no_group_var(self):
        """Check widget discrete data with missing values and no group variable"""
        data = self.zoo
        data.domain.class_var = ContinuousVariable("cls")
        data.X[:, 0] = np.nan
        self.send_signal("Data", data)

    def test_apply_sorting(self):
        controls = self.widget.controlledAttributes
        group_list = controls["group_var"][0].control
        order_check = controls["order_by_importance"][0].control
        attributes = self.widget.attrs

        def select_group(i):
            group_selection = group_list.selectionModel()
            group_selection.setCurrentIndex(
                group_list.model().index(i),
                group_selection.ClearAndSelect)

        data = self.titanic
        self.send_signal("Data", data)

        select_group(0)
        self.assertFalse(order_check.isEnabled())
        select_group(1)
        self.assertTrue(order_check.isEnabled())

        order_check.setChecked(False)
        self.assertEqual(tuple(attributes), data.domain.variables)
        order_check.setChecked(True)
        self.assertEqual([x.name for x in attributes],
                         ['sex', 'survived', 'age', 'status'])
        select_group(4)
        self.assertEqual([x.name for x in attributes],
                         ['sex', 'status', 'age', 'survived'])

        data = self.heart
        self.send_signal("Data", data)
        select_group(len(group_list.model()) - 1)
        order_check.setChecked(True)
        self.assertEqual([x.name for x in attributes],
                         ['thal', 'major vessels colored', 'chest pain',
                          'ST by exercise', 'max HR', 'exerc ind ang',
                          'slope peak exc ST', 'gender', 'age', 'rest SBP',
                          'rest ECG', 'cholesterol',
                          'fasting blood sugar > 120', 'diameter narrowing'])
