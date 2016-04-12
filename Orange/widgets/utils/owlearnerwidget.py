import numpy as np

from Orange.data import Table
from Orange.preprocess.preprocess import Preprocess
from Orange.widgets import gui
from Orange.widgets.settings import Setting
from Orange.widgets.utils.sql import check_sql_input
from Orange.widgets.widget import OWWidget, WidgetMetaClass


class DefaultWidgetChannelsMetaClass(WidgetMetaClass):
    """Metaclass that adds default inputs and outputs objects.
    """

    REQUIRED_ATTRIBUTES = []

    def __new__(mcls, name, bases, attrib):
        # check whether it is abstract class
        if attrib.get('name', False):
            # Ensure all needed attributes are present
            if not all(attr in attrib for attr in mcls.REQUIRED_ATTRIBUTES):
                raise AttributeError("'{name}' must have '{attrs}' attributes"
                                     .format(name=name, attrs="', '".join(mcls.REQUIRED_ATTRIBUTES)))

            attrib['outputs'] = mcls.update_channel(
                mcls.default_outputs(attrib),
                attrib.get('outputs', [])
            )

            attrib['inputs'] = mcls.update_channel(
                mcls.default_inputs(attrib),
                attrib.get('inputs', [])
            )

            mcls.add_extra_attributes(attrib)

        return super().__new__(mcls, name, bases, attrib)

    @classmethod
    def default_inputs(cls, attrib):
        return []

    @classmethod
    def default_outputs(cls, attrib):
        return []

    @classmethod
    def update_channel(cls, channel, items):
        item_names = set(item[0] for item in channel)

        for item in items:
            if not item[0] in item_names:
                channel.append(item)

        return channel

    @classmethod
    def add_extra_attributes(cls, attrib):
        return attrib


class DefaultLearnerWidgetChannelsMetaClass(DefaultWidgetChannelsMetaClass):
    """Metaclass that adds default inputs (table, preprocess) and
    outputs (learner, model) for learner widgets.
    """

    REQUIRED_ATTRIBUTES = ['LEARNER', 'OUTPUT_MODEL_NAME']

    @classmethod
    def default_inputs(cls, attrib):
        return [("Data", Table, "set_data"), ("Preprocessor", Preprocess, "set_preprocessor")]

    @classmethod
    def default_outputs(cls, attrib):
        return [("Learner", attrib['LEARNER']),
                (attrib['OUTPUT_MODEL_NAME'], attrib['LEARNER'].__returns__)]

    @classmethod
    def add_extra_attributes(cls, attrib):
        if attrib.get('model_name', None) is None:
            attrib['model_name'] = Setting(attrib['LEARNER'].__returns__)
        return attrib


class OWBaseLearner(OWWidget, metaclass=DefaultLearnerWidgetChannelsMetaClass):
    LEARNER = None
    OUTPUT_MODEL_NAME = None

    want_main_area = False
    resizing_enabled = False

    DATA_ERROR_ID = 1
    OUTDATED_LEARNER_WARNING_ID = 2

    def __init__(self):
        super().__init__()
        self.data = None
        self.learner = None
        self.model = None
        self.preprocessors = None
        self.outdated_settings = False
        self.setup_layout()
        self.apply()

    def set_preprocessor(self, preprocessor):
        """Add user-set preprocessors before the default, mandatory ones"""
        self.preprocessors = ((preprocessor,) if preprocessor else ()) + tuple(self.LEARNER.preprocessors)
        self.apply()

    @check_sql_input
    def set_data(self, data):
        """Set the input train data set."""
        self.error(self.DATA_ERROR_ID)
        self.data = data
        if data is not None and data.domain.class_var is None:
            self.error(self.DATA_ERROR_ID, "Data has no target variable")
            self.data = None

        self.update_model()

    def apply(self):
        self.update_learner()
        self.update_model()

    def create_learner(self):
        raise NotImplementedError()

    def update_learner(self):
        self.learner = self.create_learner()
        self.send("Learner", self.learner)
        self.outdated_settings = False
        self.warning(self.OUTDATED_LEARNER_WARNING_ID)

    def update_model(self):
        self.model = None
        self.good_data = False
        if self.data is not None:
            self.error(self.DATA_ERROR_ID)
            if not self.learner.check_learner_adequacy(self.data.domain):
                self.error(self.DATA_ERROR_ID, self.learner.learner_adequacy_err_msg)
            elif len(np.unique(self.data.Y)) < 2:
                self.error(self.DATA_ERROR_ID, "Data contains only one target value.")
            else:
                self.model = self.learner(self.data)
                self.model.name = self.learner_name
                self.model.instances = self.data
                self.good_data = True

        self.send(self.OUTPUT_MODEL_NAME, self.model)

    def settings_changed(self, *args, **kwargs):
        self.outdated_settings = True
        self.warning(self.OUTDATED_LEARNER_WARNING_ID,
                     "Press Apply to submit changes.")

    def get_model_parameters(self):
        return None

    def send_report(self):
        self.report_items((("Name", self.learner_name),))

        model_parameters = self.get_model_parameters()
        if model_parameters:
            self.report_items("Model parameters", model_parameters)

        if self.data:
            self.report_data("Data", self.data)

    # GUI
    def add_learner_name_widget(self):
        gui.lineEdit(self.controlArea, self, 'learner_name', box='Name',
                     tooltip='The name will identify this model in other widgets')

    def add_main_layout(self):
        pass

    def add_bottom_buttons(self):
        box = gui.widgetBox(self.controlArea, True, orientation="horizontal")
        box.layout().addWidget(self.report_button)
        gui.separator(box, 15)
        gui.button(box, self, "&Apply", callback=self.apply, disabled=0,
                   default=True)

    def setup_layout(self):
        self.add_learner_name_widget()
        self.add_main_layout()
        self.add_bottom_buttons()
