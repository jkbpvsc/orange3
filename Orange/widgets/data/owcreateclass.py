import numpy as np

from AnyQt.QtWidgets import QGridLayout, QLabel, QLineEdit, QSizePolicy
from AnyQt.QtCore import QSize, Qt

from Orange.data import StringVariable, DiscreteVariable, Domain
from Orange.data.table import Table
from Orange.statistics.util import bincount
from Orange.preprocess.transformation import Transformation, Lookup
from Orange.widgets import gui, widget
from Orange.widgets.settings import DomainContextHandler, ContextSetting
from Orange.widgets.utils.itemmodels import DomainModel
from Orange.widgets.widget import Msg


def map_by_substring(a, patterns, case_sensitive, at_beginning):
    res = np.full(len(a), np.nan)
    if not case_sensitive:
        a = np.char.lower(a)
        patterns = (pattern.lower() for pattern in patterns)
    for val_idx, pattern in reversed(list(enumerate(patterns))):
        indices = np.char.find(a, pattern)
        matches = indices == 0 if at_beginning else indices != -1
        res[matches] = val_idx
    return res


class ValueFromStringSubstring(Transformation):
    def __init__(self, variable, patterns,
                 case_sensitive=False, match_beginning=False):
        super().__init__(variable)
        self.patterns = patterns
        self.case_sensitive = case_sensitive
        self.match_beginning = match_beginning

    def transform(self, c):
        nans = np.equal(c, None)
        c = c.astype(str)
        c[nans] = ""
        res = map_by_substring(
            c, self.patterns, self.case_sensitive, self.match_beginning)
        res[nans] = np.nan
        return res


class ValueFromDiscreteSubstring(Lookup):
    def __init__(self, variable, patterns,
                 case_sensitive=False, match_beginning=False):
        super().__init__(variable, [])
        self.case_sensitive = case_sensitive
        self.match_beginning = match_beginning
        self.patterns = patterns  # Finally triggers computation of the lookup

    def __setattr__(self, key, value):
        super().__setattr__(key, value)
        if hasattr(self, "patterns") and \
                key in ("case_sensitive", "match_beginning", "patterns",
                        "variable"):
            self.lookup_table = map_by_substring(
                self.variable.values, self.patterns,
                self.case_sensitive, self.match_beginning)


class OWCreateClass(widget.OWWidget):
    name = "Create Class"
    description = "Create class attribute from a string attribute"
    icon = "icons/CreateClass.svg"
    category = "Data"
    keywords = ["data"]

    inputs = [("Data", Table, "set_data")]
    outputs = [("Data", Table)]

    want_main_area = False

    settingsHandler = DomainContextHandler()
    attribute = ContextSetting(None)
    rules = ContextSetting({})
    match_beginning = ContextSetting(False)
    case_sensitive = ContextSetting(False)

    TRANSFORMERS = {StringVariable: ValueFromStringSubstring,
                    DiscreteVariable: ValueFromDiscreteSubstring}

    class Warning(widget.OWWidget.Warning):
        no_nonnumeric_vars = Msg("Data contains only numeric variables.")

    def __init__(self):
        super().__init__()
        self.data = None
        self.line_edits = []
        self.remove_buttons = []
        self.counts = []
        self.match_counts = []
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        patternbox = gui.vBox(self.controlArea, box="Patterns")
        box = gui.hBox(patternbox)
        gui.widgetLabel(box, "Class from column: ", addSpace=12)
        gui.comboBox(
            box, self, "attribute", callback=self.update_rules,
            model=DomainModel(valid_types=(StringVariable, DiscreteVariable)),
            sizePolicy=(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed))

        self.rules_box = rules_box = QGridLayout()
        patternbox.layout().addLayout(self.rules_box)
        self.add_button = gui.button(None, self, "+", flat=True,
                                     callback=self.add_row,
                                     minimumSize=QSize(12, 20))
        self.rules_box.setColumnMinimumWidth(1, 80)
        self.rules_box.setColumnMinimumWidth(0, 10)
        self.rules_box.setColumnStretch(0, 1)
        self.rules_box.setColumnStretch(1, 1)
        self.rules_box.setColumnStretch(2, 100)
        rules_box.addWidget(QLabel("Name"), 0, 1)
        rules_box.addWidget(QLabel("Pattern"), 0, 2)
        rules_box.addWidget(QLabel("#Instances"), 0, 3, 1, 2)
        self.update_rules()

        optionsbox = gui.vBox(self.controlArea, box=True)
        gui.checkBox(
            optionsbox, self, "match_beginning", "Match only at the beginning",
            callback=self.options_changed)
        gui.checkBox(
            optionsbox, self, "case_sensitive", "Case sensitive",
            callback=self.options_changed)

        box = gui.hBox(self.controlArea)
        gui.rubber(box)
        gui.button(box, self, "Apply", autoDefault=False, callback=self.apply)

    @property
    def active_rules(self):
        return self.rules.setdefault(self.attribute and self.attribute.name,
                                     [["C1", ""], ["C2", ""]])

    def rules_to_edits(self):
        for editr, textr in zip(self.line_edits, self.active_rules):
            for edit, text in zip(editr, textr):
                edit.setText(text)

    def set_data(self, data):
        self.closeContext()
        self.rules = {}
        self.data = data
        model = self.controls.attribute.model()
        model.set_domain(data and data.domain)
        self.Warning.no_nonnumeric_vars(shown=data is not None and not model)
        if not model:
            self.attribute = None
            self.send("Data", None)
            return
        self.attribute = model[0]
        self.openContext(data)
        self.update_rules()
        self.apply()

    def update_rules(self):
        self.adjust_n_rule_rows()
        self.rules_to_edits()
        self.update_counts()

    def options_changed(self):
        self.update_counts()

    def adjust_n_rule_rows(self):
        def _add_line():
            self.line_edits.append([])
            n_lines = len(self.line_edits)
            for coli in range(1, 3):
                edit = QLineEdit()
                self.line_edits[-1].append(edit)
                self.rules_box.addWidget(edit, n_lines, coli)
                edit.textChanged.connect(self.sync_edit)
            button = gui.button(
                None, self, label='×', flat=True, height=20,
                styleSheet='* {font-size: 16pt; color: silver}'
                           '*:hover {color: black}',
                callback=self.remove_row)
            button.setMinimumSize(QSize(12, 20))
            self.remove_buttons.append(button)
            self.rules_box.addWidget(button, n_lines, 0)
            self.counts.append([])
            for coli, kwargs in enumerate(
                    (dict(alignment=Qt.AlignRight),
                     dict(alignment=Qt.AlignLeft, styleSheet="color: gray"))):
                label = QLabel(**kwargs)
                self.counts[-1].append(label)
                self.rules_box.addWidget(label, n_lines, 3 + coli)

        def _remove_line():
            for edit in self.line_edits.pop():
                edit.deleteLater()
            self.remove_buttons.pop().deleteLater()
            for label in self.counts.pop():
                label.deleteLater()

        def _fix_tab_order():
            prev = None
            for row, rule in zip(self.line_edits, self.active_rules):
                for col_idx, edit in enumerate(row):
                    edit.row, edit.col_idx = rule, col_idx
                    if prev is not None:
                        self.setTabOrder(prev, edit)
                    prev = edit

        n = len(self.active_rules)
        while n > len(self.line_edits):
            _add_line()
        while len(self.line_edits) > n:
            _remove_line()
        self.rules_box.addWidget(self.add_button, n + 1, 0)
        _fix_tab_order()

    def add_row(self):
        self.active_rules.append(["", ""])
        self.adjust_n_rule_rows()

    def remove_row(self):
        remove_idx = self.remove_buttons.index(self.sender())
        del self.active_rules[remove_idx]
        self.update_rules()

    def sync_edit(self, text):
        edit = self.sender()
        edit.row[edit.col_idx] = text
        self.update_counts()

    def update_counts(self):
        def _matcher(strings, pattern):
            if not self.case_sensitive:
                pattern = pattern.lower()
            indices = np.char.find(strings, pattern)
            return indices == 0 if self.match_beginning else indices != -1

        def _lower_if_needed(strings):
            return strings if self.case_sensitive else np.char.lower(strings)

        def _string_counts():
            nonlocal data
            data = data.astype(str)
            data = data[~np.char.equal(data, "")]
            data = _lower_if_needed(data)
            remaining = np.array(data)
            for _, pattern in self.active_rules:
                matching = _matcher(remaining, pattern)
                total_matching = _matcher(data, pattern)
                yield matching, total_matching
                remaining = remaining[~matching]
                if len(remaining) == 0:
                    break

        def _discrete_counts():
            attr_vals = np.array(attr.values)
            attr_vals = _lower_if_needed(attr_vals)
            bins = bincount(data, max_val=len(attr.values) - 1)[0]
            remaining = np.array(bins)
            for _, pattern in self.active_rules:
                matching = _matcher(attr_vals, pattern)
                yield remaining[matching], bins[matching]
                remaining[matching] = 0
                if not np.any(remaining):
                    break

        def _clear_labels():
            for lab_matched, lab_total in self.counts:
                lab_matched.setText("")
                lab_total.setText("")

        def _set_labels():
            for (n_matched, n_total), (lab_matched, lab_total) in \
                    zip(self.match_counts, self.counts):
                n_before = n_total - n_matched
                lab_matched.setText("{}".format(n_matched))
                if n_before:
                    lab_total.setText("+ {}".format(n_before))

        _clear_labels()
        attr = self.attribute
        if attr is None:
            return
        counters = {StringVariable: _string_counts,
                    DiscreteVariable: _discrete_counts}
        data = self.data.get_column_view(attr)[0]
        self.match_counts = [[int(np.sum(x)) for x in matches]
                             for matches in counters[type(attr)]()]
        _set_labels()

    def apply(self):
        if not self.attribute or not self.active_rules:
            self.send("Data", None)
            return
        domain = self.data.domain
        # Transposition + stripping
        names, patterns = \
            zip(*((name.strip(), pattern)
                  for name, pattern in self.active_rules if name.strip()))
        transformer = self.TRANSFORMERS[type(self.attribute)]
        compute_value = transformer(
            self.attribute, patterns, self.case_sensitive, self.match_beginning)
        new_class = DiscreteVariable(
            "class", names, compute_value=compute_value)
        new_domain = Domain(
            domain.attributes, new_class, domain.metas + domain.class_vars)
        new_data = Table(new_domain, self.data)
        self.send("Data", new_data)


def main():  # pragma: no cover
    import sys
    from AnyQt.QtWidgets import QApplication

    a = QApplication(sys.argv)
    table = Table("zoo")
    ow = OWCreateClass()
    ow.show()
    ow.set_data(table)
    a.exec()
    ow.saveSettings()

if __name__ == "__main__":  # pragma: no cover
    main()
