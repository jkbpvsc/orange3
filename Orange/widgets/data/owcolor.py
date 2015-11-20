import copy

from PyQt4.QtCore import Qt, QAbstractTableModel, SIGNAL
from PyQt4.QtGui import QStyledItemDelegate, QColor, QHeaderView, QFont, \
    QColorDialog, QTableView, qRgb, QImage
import numpy as np

import Orange
from Orange.widgets import widget, settings, gui
from Orange.widgets.utils.colorpalette import ColorPaletteGenerator, \
    ContinuousPaletteGenerator, ColorPaletteDlg

ColorRole = next(gui.OrangeUserRole)


class HorizontalGridDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        painter.setPen(QColor(212, 212, 212))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        painter.restore()
        QStyledItemDelegate.paint(self, painter, option, index)


# noinspection PyMethodOverriding
class ColorTableModel(QAbstractTableModel):
    def __init__(self):
        QAbstractTableModel.__init__(self)
        self.variables = []

    @staticmethod
    def _encode_color(color):
        return "#{}{}{}".format(*[("0" + hex(x)[2:])[-2:] for x in color])

    def flags(self, _):
        return Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def set_data(self, variables):
        self.variables = variables
        self.emit(SIGNAL("dataChanged(QModelIndex, QModelIndex)"),
                  self.index(0, 0), self.index(self.n_columns(), self.n_rows()))

    def rowCount(self, parent):
        return 0 if parent.isValid() else self.n_rows()

    def columnCount(self, parent):
        return 0 if parent.isValid() else self.n_columns()

    def n_rows(self):
        return len(self.variables)

    def data(self, index, role=Qt.DisplayRole):
        # Only valid for the first column
        row = index.row()
        if role == Qt.DisplayRole or role == Qt.EditRole:
            return self.variables[row].name
        if role == Qt.FontRole:
            font = QFont()
            font.setBold(True)
            return font
        if role == Qt.TextAlignmentRole:
            return Qt.AlignRight | Qt.AlignVCenter

    def setData(self, index, value, role):
        # Only valid for the first column
        if role == Qt.EditRole:
            self.variables[index.row()].name = value
        else:
            return False
        self.emit(SIGNAL("dataChanged(QModelIndex, QModelIndex)"), index, index)
        return True


class DiscColorTableModel(ColorTableModel):
    def n_columns(self):
        return bool(self.variables) and \
               1 + max(len(var.values) for var in self.variables)

    def data(self, index, role=Qt.DisplayRole):
        row, col = index.row(), index.column()
        if col == 0:
            return ColorTableModel.data(self, index, role)
        var = self.variables[row]
        if col > len(var.values):
            return
        if role == Qt.DisplayRole or role == Qt.EditRole:
            return var.values[col - 1]
        color = var.colors[col - 1]
        if role == Qt.DecorationRole:
            return QColor(*color)
        if role == Qt.ToolTipRole:
            return self._encode_color(color)
        if role == ColorRole:
            return var.colors[col - 1]

    # noinspection PyMethodOverriding
    def setData(self, index, value, role):
        row, col = index.row(), index.column()
        if col == 0:
            return ColorTableModel.setData(self, index, value, role)
        if role == ColorRole:
            self.variables[row].colors[col - 1][:] = value[:3]
        elif role == Qt.EditRole:
            self.variables[row].values[col - 1] = value
        else:
            return False
        self.emit(SIGNAL("dataChanged(QModelIndex, QModelIndex)"), index, index)
        return True


class ContColorTableModel(ColorTableModel):
    @staticmethod
    def n_columns():
        return 2

    def data(self, index, role=Qt.DisplayRole):
        row, col = index.row(), index.column()
        if col == 0:
            return ColorTableModel.data(self, index, role)
        if col > 1:
            return
        var = self.variables[row]
        if role == Qt.DecorationRole:
            continuous_palette = ContinuousPaletteGenerator(*var.colors)
            line = continuous_palette.getRGB(np.arange(0, 1, 1 / 256))
            data = np.arange(0, 256, dtype=np.int8).\
                reshape((1, 256)).\
                repeat(16, 0)
            img = QImage(data, 256, 16, QImage.Format_Indexed8)
            img.setColorCount(256)
            img.setColorTable([qRgb(*x) for x in line])
            img.data = data
            return img
        if role == Qt.ToolTipRole:
            return "{} - {}".format(self._encode_color(var.colors[0]),
                                    self._encode_color(var.colors[1]))
        if role == ColorRole:
            return var.colors

    # noinspection PyMethodOverriding
    def setData(self, index, value, role):
        row, col = index.row(), index.column()
        if col == 0:
            return ColorTableModel.setData(self, index, value, role)
        if role == ColorRole:
            self.variables[row].colors = value
        else:
            return False
        self.emit(SIGNAL("dataChanged(QModelIndex, QModelIndex)"), index, index)
        return True


class ColorTable(QTableView):
    def __init__(self, model):
        QTableView.__init__(self)
        self.horizontalHeader().hide()
        self.verticalHeader().hide()
        self.setShowGrid(False)
        self.setSelectionMode(QTableView.NoSelection)
        self.setItemDelegate(HorizontalGridDelegate())
        self.horizontalHeader().setResizeMode(QHeaderView.ResizeToContents)
        self.setModel(model)

    def mouseReleaseEvent(self, ev):
        index = self.indexAt(ev.pos())
        rect = self.visualRect(index)
        self.handle_click(index, ev.pos().x() - rect.x())


class DiscreteTable(ColorTable):
    def handle_click(self, index, x_offset):
        if index.column() == 0 or x_offset > 24:
            self.edit(index)
        else:
            self.change_color(index)

    def change_color(self, index):
        color = self.model().data(index, ColorRole)
        if color is None:
            return
        dlg = QColorDialog(QColor(*color))
        if dlg.exec():
            color = dlg.selectedColor()
            self.model().setData(index, color.getRgb(), ColorRole)


class ContinuousTable(ColorTable):
    def __init__(self, master, model):
        ColorTable.__init__(self, model)
        self.master = master

    def handle_click(self, index, _):
        if index.column() == 0:
            self.edit(index)
        else:
            self.change_color(index)

    def change_color(self, index):
        from_c, to_c, black = self.model().data(index, ColorRole)
        master = self.master
        dlg = ColorPaletteDlg(master)
        dlg.createContinuousPalette("", "Gradient palette", black,
                                    QColor(*from_c), QColor(*to_c))
        dlg.setColorSchemas(master.color_settings, master.selected_schema_index)
        if dlg.exec():
            self.model().setData(index,
                                 (dlg.contLeft.getColor().getRgb(),
                                  dlg.contRight.getColor().getRgb(),
                                  dlg.contpassThroughBlack),
                                 ColorRole)
            master.color_settings = dlg.getColorSchemas()
            master.selected_schema_index = dlg.selectedSchemaIndex


class OWColor(widget.OWWidget):
    name = "Color"
    description = "Set color legend for variables"
    icon = "icons/Colors.svg"

    inputs = [("Data", Orange.data.Table, "set_data")]
    outputs = [("Data", Orange.data.Table)]

    settingsHandler = settings.PerfectDomainContextHandler()
    disc_colors = settings.ContextSetting([])
    cont_colors = settings.ContextSetting([])
    color_settings = settings.Setting(None)
    selected_schema_index = settings.Setting(0)

    want_main_area = False

    def __init__(self):
        super().__init__()
        self.data = None
        self.disc_colors = []
        self.cont_colors = []

        box = gui.widgetBox(self.controlArea, "Discrete variables",
                            orientation="horizontal")
        self.disc_model = DiscColorTableModel()
        self.disc_view = DiscreteTable(self.disc_model)
        box.layout().addWidget(self.disc_view)

        box = gui.widgetBox(self.controlArea, "Numeric variables",
                            orientation="horizontal")
        self.cont_model = ContColorTableModel()
        self.cont_view = ContinuousTable(self, self.cont_model)
        box.layout().addWidget(self.cont_view)

    def set_data(self, data):
        self.disc_colors = []
        self.cont_colors = []
        if data is None:
            self.data = None
        else:
            def create_part(variables):
                vars = []
                for i, var in enumerate(variables):
                    if not (var.is_discrete or var.is_continuous):
                        vars.append(var)
                        continue
                    var = var.make_proxy()
                    if hasattr(var, "colors"):
                        var.colors = copy.copy(var.colors)
                    if var.is_discrete:
                        var.values = var.values[:]
                        if not hasattr(var, "colors"):
                            n_values = len(var.values)
                            palette = ColorPaletteGenerator(n_values)
                            var.colors = palette.getRGB(range(n_values))
                        # TODO: This is OK for model, but not for settings
                        self.disc_colors.append(var)
                    else:
                        if not hasattr(var, "colors"):
                            var.colors = ((0, 0, 255), (255, 255, 0), False)
                        # TODO: This is OK for model, but not for settings
                        self.cont_colors.append(var)
                    vars.append(var)
                return vars

            domain = data.domain
            domain = Orange.data.Domain(create_part(domain.attributes),
                                        create_part(domain.class_vars),
                                        create_part(domain.metas))
            self.data = Orange.data.Table(domain, data)
            self.disc_model.set_data(self.disc_colors)
            self.cont_model.set_data(self.cont_colors)
            self.disc_view.resizeColumnsToContents()
            self.cont_view.resizeColumnsToContents()
        self.commit()

    def commit(self):
        self.send("Data", self.data)


if __name__ == "__main__":
    from PyQt4 import QtGui
    a = QtGui.QApplication([])
    ow = OWColor()
    ow.set_data(Orange.data.Table("heart_disease.tab"))
    ow.show()
    a.exec_()
    ow.saveSettings()
