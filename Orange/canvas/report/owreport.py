import os
import time
import tempfile
import shutil
import pkg_resources
from PyQt4.QtCore import Qt, QUrl
from PyQt4.QtGui import (QApplication, QDialog, QPrinter, QIcon,
                         QPrintDialog, QFileDialog, QMenu)
from Orange.widgets import gui
from Orange.widgets.widget import OWWidget
from Orange.widgets.settings import Setting
from Orange.widgets.io import PngFormat


class OWReport(OWWidget):
    name = "Report"
    save_dir = Setting("")
    report_url_pref = "file:///"
    report_temp_dir = tempfile.mkdtemp("", "Orange3_report")

    def __init__(self):
        super().__init__()
        # TODO - ko kliknes na webview, oznaci item
        self.widget_list_items = []
        self.widget_list = gui.listBox(
            self.controlArea, self,
            labels="widget_list_items", callback=self._reload,
            enableDragDrop=True, dragDropCallback=self._reload
        )
        self.widget_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.widget_list.customContextMenuRequested.connect(self._show_menu)

        self.save_button = gui.button(
            self.controlArea, self, "Save",
            callback=self._save_report, default=True
        )
        self.print_button = gui.button(
            self.controlArea, self, "Print", callback=self._print_report
        )

        self.report_view_items = {}
        self.report_view = gui.WebviewWidget(self.mainArea)
        frame = self.report_view.page().mainFrame()
        frame.setScrollBarPolicy(Qt.Vertical, Qt.ScrollBarAsNeeded)
        self.javascript = frame.evaluateJavaScript

        index_file = pkg_resources.resource_filename(__name__, "index.html")
        self.report_html_template = open(index_file, "r").read()

        self.setModal(False)

    def _reload(self):
        self._build_html()

    def _show_menu(self, pos):
        widget_list_menu = QMenu(self)
        widget_list_menu.addAction("Remove", self._remove_widget_item)
        widget_list_menu.addAction("Remove All", self._clear)
        widget_list_menu.popup(self.mapToGlobal(pos))

    def _clear(self):
        self.widget_list_items = []
        self.report_view_items = {}
        self._build_html()

    def _remove_widget_item(self):
        selected_row = self.widget_list.currentRow()
        if selected_row >= 0:
            items = self.widget_list_items
            selected_item = items.pop(selected_row)
            self.widget_list_items = items
            del self.report_view_items[selected_item]
            if selected_row < len(self.report_view_items):
                self.widget_list.setCurrentRow(selected_row)
            self._build_html()

    def _add_widget_item(self, widget):
        items = self.widget_list_items
        path = pkg_resources.resource_filename(widget.__module__, widget.icon)
        icon = QIcon(path)
        items.append((widget.name, icon))
        self.report_view_items[(widget.name, icon)] = widget.report_html
        self.widget_list_items = items

    def _build_html(self):
        n_widgets = len(self.widget_list_items)
        if not n_widgets:
            return

        selected_row = self.widget_list.currentRow()
        if selected_row < 0 and n_widgets:
            selected_row = n_widgets - 1
            self.widget_list.setCurrentRow(selected_row)

        html = self.report_html_template
        html += "<body>"
        for i, (item_name, item_icon) in enumerate(self.widget_list_items):
            html += "<div id='%s' class='%s'>%s</div>" % (
                id(item_icon),
                "selected" if i == selected_row else "normal",
                self.report_view_items[(item_name, item_icon)]
            )
        html += "</body></html>"
        self.report_view.setHtml(html, QUrl(self.report_url_pref))

        if selected_row < len(self.widget_list_items):
            self.javascript(
                "document.getElementById('%s').scrollIntoView();"
                % id(self.widget_list_items[selected_row][1]))

    def make_report(self, widget):
        self._add_widget_item(widget)
        self._build_html()

    @staticmethod
    def get_html_section(name):
        datetime = time.strftime("%a %b %d %y, %H:%M:%S")
        return "<h1>%s <span class='timestamp'>%s</h1>" % (name, datetime)

    @staticmethod
    def get_html_subsection(name):
        return "<h2>%s</h2>" % name

    @staticmethod
    def get_html_paragraph(items):
        return "<ul>" + "".join("<b>%s:</b> %s</br>" % i
                                for i in items) + "</ul>"

    @staticmethod
    def get_html_img(scene):
        filename = OWReport._get_unique_filename(OWReport.get_instance(),
                                                 "img", "png")
        writer = PngFormat()
        writer.write(filename, scene)
        return "<ul><img src='%s%s'/></ul>" % (OWReport.report_url_pref,
                                               filename)

    @staticmethod
    def clip_string(s, limit=1000, sep=None):
        if len(s) < limit:
            return s
        s = s[:limit - 3]
        if sep is None:
            return s
        sep_pos = s.rfind(sep)
        if sep_pos == -1:
            return s
        return s[:sep_pos + len(sep)] + "..."

    @staticmethod
    def clipped_list(s, limit=1000):
        return OWReport.clip_string(", ".join(s), limit, ", ")

    def _get_unique_filename(self, name, ext):
        for i in range(1000000):
            filename = os.path.join(self.report_temp_dir,
                                    "%s%f.%s" % (name, i, ext))
            if not os.path.exists(filename):
                return filename

    def _remove_temp_dir(self):
        shutil.rmtree(self.report_temp_dir)

    def _save_report(self):
        filename = QFileDialog.getSaveFileName(self, "Save Report",
                                               self.save_dir,
                                               "PDF (*.pdf)")
        if not filename:
            return

        self.save_dir = os.path.dirname(filename)
        self.saveSettings()
        printer = QPrinter()
        printer.setPageSize(QPrinter.A4)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(filename)
        self.report_view.print_(printer)

    def _print_report(self):
        printer = QPrinter()
        print_dialog = QPrintDialog(printer, self)
        print_dialog.setWindowTitle("Print report")
        if print_dialog.exec_() != QDialog.Accepted:
            return
        self.report_view.print_(printer)

    @staticmethod
    def get_instance():
        app_inst = QApplication.instance()
        if not hasattr(app_inst, "_report_window"):
            report = OWReport()
            app_inst._report_window = report
            app_inst.sendPostedEvents(report, 0)
            app_inst.aboutToQuit.connect(report._remove_temp_dir)
            app_inst.aboutToQuit.connect(report.deleteLater)
        return app_inst._report_window


if __name__ == "__main__":
    import sys
    from Orange.data import Table
    from Orange.widgets.data.owfile import OWFile
    from Orange.widgets.data.owtable import OWDataTable
    from Orange.widgets.data.owdiscretize import OWDiscretize
    from Orange.widgets.classify.owrandomforest import OWRandomForest

    iris = Table("iris")
    zoo = Table("zoo")
    app = QApplication(sys.argv)

    main = OWReport.get_instance()
    file = OWFile()
    file.create_report_html()
    main.make_report(file)

    table = OWDataTable()
    table.create_report_html()
    main.make_report(table)

    main = OWReport.get_instance()
    disc = OWDiscretize()
    disc.set_data(zoo)
    disc.create_report_html()
    main.make_report(disc)
    file = OWFile()
    file.create_report_html()
    main.make_report(file)

    rf = OWRandomForest()
    rf.set_data(iris)
    rf.create_report_html()
    main.make_report(rf)

    main.show()
    main.saveSettings()
    assert len(main.widget_list_items) == 5

    sys.exit(app.exec_())

    # DATA - File, Discretize, Continuize, Impute, DataTable, Rank, Concatenate, SelectRows, SelectColumns, DataSampler

    # VISUALIZE - Distributions, BoxPlot, ScatterMap, ScatterPlot, Mosaic, Parallel, Linear, HeatMap, Sieve, Venn

    # CLASSIFY - ClassificationTree, ClassificationTreeViewer, SVM, NN, Logistic, Bayes, RForest, Majority

    # REGRESSION - NN, Linear, Mean, Stochastic, Univariate, SVM

    # EVALUATE - vse..

    # UNSUPERVISED - ...
