from functools import reduce
import sys
import time
import os
from PyQt4.QtCore import QByteArray, Qt, pyqtSignal as Signal, pyqtProperty, SIGNAL, QDir
from PyQt4.QtGui import QDialog, QPixmap, QLabel, QVBoxLayout, QSizePolicy, \
    qApp, QFrame, QStatusBar, QHBoxLayout, QIcon, QTabWidget

from Orange.canvas.utils import environ
from Orange.widgets import settings, gui
from Orange.canvas.registry.description import (
    Default, NonDefault, Single, Multiple, Explicit, Dynamic,
    InputSignal, OutputSignal
)
from Orange.canvas.scheme.widgetsscheme import (
    SignalLink, WidgetsSignalManager, SignalWrapper
)
from Orange.widgets.gui import ControlledAttributesDict, notify_changed
from Orange.widgets.settings import SettingsHandler
from Orange.widgets.utils.concurrent import AsyncCall





# these definitions are needed to define Table as subclass of TableWithClass
from Orange.widgets.utils.constants import SETTINGS_HANDLER


class AttributeList(list):
    pass


class ExampleList(list):
    pass


class WidgetMetaClass(type(QDialog)):
    """Meta class for widgets. If the class definition does not have a
       specific settings handler, the meta class provides a default one
       that does not handle contexts. Then it scans for any attributes
       of class settings.Setting: the setting is stored in the handler and
       the value of the attribute is replaced with the default."""

    #noinspection PyMethodParameters
    def __new__(mcs, name, bases, dict):
        from Orange.canvas.registry.description import (
            input_channel_from_args, output_channel_from_args)

        cls = type.__new__(mcs, name, bases, dict)
        if not cls.name: # not a widget
            return cls

        cls.inputs = list(map(input_channel_from_args, cls.inputs))
        cls.outputs = list(map(output_channel_from_args, cls.outputs))

        # TODO Remove this when all widgets are migrated to Orange 3.0
        if (hasattr(cls, "settingsToWidgetCallback") or
                hasattr(cls, "settingsFromWidgetCallback")):
            raise SystemError("Reimplement settingsToWidgetCallback and "
                              "settingsFromWidgetCallback")

        cls.settingsHandler = SettingsHandler.create(cls, template=cls.settingsHandler)
        for name, provider in cls.settingsHandler.default_provider.providers.items():
            delattr(cls, name)

        return cls


class OWWidget(QDialog, metaclass=WidgetMetaClass):
    # Global widget count
    widget_id = 0

    # Widget description
    name = None
    id = None
    category = None
    version = None
    description = None
    long_description = None
    icon = "icons/Unknown.png"
    priority = sys.maxsize
    author = None
    author_email = None
    maintainer = None
    maintainer_email = None
    help = None
    help_ref = None
    url = None
    keywords = []
    background = None
    replaces = None
    inputs = []
    outputs = []

    # Default widget layout settings
    want_basic_layout = True
    want_main_area = True
    want_control_area = True
    want_graph = False
    show_save_graph = True
    want_status_bar = False
    no_report = False

    save_position = False
    resizing_enabled = True

    widgetStateChanged = Signal(str, int, str)
    blockingStateChanged = Signal(bool)
    asyncCallsStateChange = Signal()
    progressBarValueChanged = Signal(float)
    processingStateChanged = Signal(int)

    settingsHandler = None

    def __new__(cls, parent=None, *args, **kwargs):
        self = super().__new__(cls, None, cls.get_flags())
        QDialog.__init__(self, None, self.get_flags())

        # 'current_context' MUST be the first thing assigned to a widget
        self.current_context = settings.Context()
        if self.settingsHandler:
            stored_settings = kwargs.get('stored_settings', None)
            self.settingsHandler.initialize(self, stored_settings)

        # number of control signals that are currently being processed
        # needed by signalWrapper to know when everything was sent
        self.needProcessing = 0     # used by signalManager
        self.signalManager = kwargs.get('signal_manager', None)

        setattr(self, gui.CONTROLLED_ATTRIBUTES, ControlledAttributesDict(self))
        self._guiElements = []      # used for automatic widget debugging
        self.__reportData = None

        # TODO: position used to be saved like this. Reimplement.
        #if save_position:
        #    self.settingsList = getattr(self, "settingsList", []) + \
        #                        ["widgetShown", "savedWidgetGeometry"]

        OWWidget.widget_id += 1
        self.widget_id = OWWidget.widget_id

        #TODO: kill me
        self.__dict__.update(environ.directories)

        if self.name:
            self.setCaption(self.name.replace("&", ""))
        self.setFocusPolicy(Qt.StrongFocus)

        self.wrappers = [] # stored wrappers for widget events
        self.linksIn = {}  # signalName : (dirty, widFrom, handler, signalData)
        self.linksOut = {} # signalName: (signalData, id)
        self.connections = {} # keys are (control, signal) and values are
        # wrapper instances. Used in connect/disconnect
        self.progressBarHandler = None  # handler for progress bar events
        self.processingHandler = None   # handler for processing events
        self.eventHandler = None
        self.callbackDeposit = []
        self.startTime = time.time()    # used in progressbar

        self.widgetStateHandler = None
        self.widgetState = {"Info": {}, "Warning": {}, "Error": {}}

        self._private_thread_pools = {}
        self.asyncCalls = []
        self.asyncBlock = False

        if self.want_basic_layout:
            self.insertLayout()

        return self

    def __init__(self, *args, **kwargs):
        """QDialog __init__ was already called in __new__,
        please do not call it here."""

    @classmethod
    def get_flags(cls):
        return (Qt.Window if cls.resizing_enabled
                else Qt.Dialog | Qt.MSWindowsFixedSizeDialogHint)

    def insertLayout(self):
        def createPixmapWidget(self, parent, iconName):
            w = QLabel(parent)
            parent.layout().addWidget(w)
            w.setFixedSize(16, 16)
            w.hide()
            if os.path.exists(iconName):
                w.setPixmap(QPixmap(iconName))
            return w

        self.setLayout(QVBoxLayout())
        self.layout().setMargin(2)

        self.topWidgetPart = gui.widgetBox(self,
                                           orientation="horizontal", margin=0)
        self.leftWidgetPart = gui.widgetBox(self.topWidgetPart,
                                            orientation="vertical", margin=0)
        if self.want_main_area:
            self.leftWidgetPart.setSizePolicy(
                QSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding))
            self.leftWidgetPart.updateGeometry()
            self.mainArea = gui.widgetBox(self.topWidgetPart,
                                          orientation="vertical",
                                          sizePolicy=QSizePolicy(QSizePolicy.Expanding,
                                                                 QSizePolicy.Expanding),
                                          margin=0)
            self.mainArea.layout().setMargin(4)
            self.mainArea.updateGeometry()

        if self.want_control_area:
            self.controlArea = gui.widgetBox(self.leftWidgetPart,
                                             orientation="vertical", margin=4)

        if self.want_graph and self.show_save_graph:
            graphButtonBackground = gui.widgetBox(self.leftWidgetPart,
                                                  orientation="horizontal", margin=4)
            self.graphButton = gui.button(graphButtonBackground,
                                          self, "&Save Graph")
            self.graphButton.setAutoDefault(0)

        if self.want_status_bar:
            self.widgetStatusArea = QFrame(self)
            self.statusBarIconArea = QFrame(self)
            self.widgetStatusBar = QStatusBar(self)

            self.layout().addWidget(self.widgetStatusArea)

            self.widgetStatusArea.setLayout(QHBoxLayout(self.widgetStatusArea))
            self.widgetStatusArea.layout().addWidget(self.statusBarIconArea)
            self.widgetStatusArea.layout().addWidget(self.widgetStatusBar)
            self.widgetStatusArea.layout().setMargin(0)
            self.widgetStatusArea.setFrameShape(QFrame.StyledPanel)

            self.statusBarIconArea.setLayout(QHBoxLayout())
            self.widgetStatusBar.setSizeGripEnabled(0)

            self.statusBarIconArea.hide()

            self._warningWidget = createPixmapWidget(self.statusBarIconArea,
                                                     os.path.join(self.widgetDir, "icons/triangle-orange.png"))
            self._errorWidget = createPixmapWidget(self.statusBarIconArea,
                                                   os.path.join(self.widgetDir + "icons/triangle-red.png"))


    # status bar handler functions
    def setState(self, stateType, id, text):
        stateChanged = super().setState(stateType, id, text)
        if not stateChanged or not hasattr(self, "widgetStatusArea"):
            return

        iconsShown = 0
        warnings = [("Warning", self._warningWidget, self._owWarning),
                    ("Error", self._errorWidget, self._owError)]
        for state, widget, use in warnings:
            if not widget:
                continue
            if use and self.widgetState[state]:
                widget.setToolTip("\n".join(self.widgetState[state].values()))
                widget.show()
                iconsShown = 1
            else:
                widget.setToolTip("")
                widget.hide()

        if iconsShown:
            self.statusBarIconArea.show()
        else:
            self.statusBarIconArea.hide()

        if (stateType == "Warning" and self._owWarning) or \
                (stateType == "Error" and self._owError):
            if text:
                self.setStatusBarText(stateType + ": " + text)
            else:
                self.setStatusBarText("")
        self.updateStatusBarState()

    def updateWidgetStateInfo(self, stateType, id, text):
        html = self.widgetStateToHtml(self._owInfo, self._owWarning,
                                      self._owError)
        if html:
            self.widgetStateInfoBox.show()
            self.widgetStateInfo.setText(html)
            self.widgetStateInfo.setToolTip(html)
        else:
            if not self.widgetStateInfoBox.isVisible():
                dHeight = - self.widgetStateInfoBox.height()
            else:
                dHeight = 0
            self.widgetStateInfoBox.hide()
            self.widgetStateInfo.setText("")
            self.widgetStateInfo.setToolTip("")
            width, height = self.width(), self.height() + dHeight
            self.resize(width, height)

    def updateStatusBarState(self):
        if not hasattr(self, "widgetStatusArea"):
            return
        if self.widgetState["Warning"] or self.widgetState["Error"]:
            self.widgetStatusArea.show()
        else:
            self.widgetStatusArea.hide()

    def setStatusBarText(self, text, timeout=5000):
        if hasattr(self, "widgetStatusBar"):
            self.widgetStatusBar.showMessage(" " + text, timeout)

    # TODO add!
    def prepareDataReport(self, data):
        pass


    def getIconNames(self, iconName):
        # if canvas sent us a prepared list of valid names, just return those
        if type(iconName) == list:
            return iconName

        names = []
        name, ext = os.path.splitext(iconName)
        for num in [16, 32, 42, 60]:
            names.append("%s_%d%s" % (name, num, ext))
        fullPaths = []
        module_dir = os.path.dirname(sys.modules[self.__module__].__file__)
        for paths in [(self.widgetDir, name),
                      (self.widgetDir, "icons", name),
                      (module_dir, "icons", name)]:
            for name in names + [iconName]:
                fname = os.path.join(*paths)
                if os.path.exists(fname):
                    fullPaths.append(fname)
            if fullPaths != []:
                break

        if len(fullPaths) > 1 and fullPaths[-1].endswith(iconName):
            # if we have the new icons we can remove the default icon
            fullPaths.pop()
        return fullPaths


    def setWidgetIcon(self, iconName):
        iconNames = self.getIconNames(iconName)
        icon = QIcon()
        for name in iconNames:
            pix = QPixmap(name)
            icon.addPixmap(pix)

        self.setWindowIcon(icon)


    # ##############################################
    def isDataWithClass(self, data, wantedVarType=None, checkMissing=False):
        self.error([1234, 1235, 1236])
        if not data:
            return 0
        if not data.domain.classVar:
            self.error(1234, "A data set with a class attribute is required.")
            return 0
        if wantedVarType and data.domain.classVar.varType != wantedVarType:
            self.error(1235, "Unable to handle %s class." %
                             str(data.domain.class_var.var_type).lower())
            return 0
        if checkMissing and not orange.Preprocessor_dropMissingClasses(data):
            self.error(1236, "Unable to handle data set with no known classes")
            return 0
        return 1

    # call processEvents(), but first remember position and size of widget in
    # case one of the events would be move or resize
    # call this function if needed in __init__ of the widget
    def safeProcessEvents(self):
        keys = ["widgetShown"]
        vals = [(key, getattr(self, key, None)) for key in keys]
        qApp.processEvents()
        for (key, val) in vals:
            if val != None:
                setattr(self, key, val)


    # this function is called at the end of the widget's __init__ when the
    # widgets is saving its position and size parameters
    def restoreWidgetPosition(self):
        if self.save_position:
            geometry = getattr(self, "savedWidgetGeometry", None)
            restored = False
            if geometry is not None:
                restored = self.restoreGeometry(QByteArray(geometry))

            if restored:
                space = qApp.desktop().availableGeometry(self)
                frame, geometry = self.frameGeometry(), self.geometry()

                #Fix the widget size to fit inside the available space
                width = space.width() - (frame.width() - geometry.width())
                width = min(width, geometry.width())
                height = space.height() - (frame.height() - geometry.height())
                height = min(height, geometry.height())
                self.resize(width, height)

                #Move the widget to the center of available space if it is
                # currently outside it
                if not space.contains(self.frameGeometry()):
                    x = max(0, space.width() / 2 - width / 2)
                    y = max(0, space.height() / 2 - height / 2)

                    self.move(x, y)


    # this is called in canvas when loading a schema. it opens the widgets
    # that were shown when saving the schema
    def restoreWidgetStatus(self):
        if self.save_position and getattr(self, "widgetShown", None):
            self.show()

    # when widget is resized, save new width and height into widgetWidth and
    # widgetHeight. some widgets can put this two variables into settings and
    # last widget shape is restored after restart
    def resizeEvent(self, ev):
        QDialog.resizeEvent(self, ev)
        # Don't store geometry if the widget is not visible
        # (the widget receives the resizeEvent before showEvent and we must not
        # overwrite the the savedGeometry before then)
        if self.save_position and self.isVisible():
            self.savedWidgetGeometry = str(self.saveGeometry())


    # set widget state to hidden
    def hideEvent(self, ev):
        if self.save_position:
            self.widgetShown = 0
            self.savedWidgetGeometry = str(self.saveGeometry())
        QDialog.hideEvent(self, ev)

    # set widget state to shown
    def showEvent(self, ev):
        QDialog.showEvent(self, ev)
        if self.save_position:
            self.widgetShown = 1
        self.restoreWidgetPosition()

    def closeEvent(self, ev):
        if self.save_position:
            self.savedWidgetGeometry = str(self.saveGeometry())
        QDialog.closeEvent(self, ev)

    def wheelEvent(self, event):
        """ Silently accept the wheel event. This is to ensure combo boxes
        and other controls that have focus don't receive this event unless
        the cursor is over them.
        """
        event.accept()

    def setCaption(self, caption):
        if self.parent != None and isinstance(self.parent, QTabWidget):
            self.parent.setTabText(self.parent.indexOf(self), caption)
        else:
            # we have to save caption title in case progressbar will change it
            self.captionTitle = str(caption)
            self.setWindowTitle(caption)

    # put this widget on top of all windows
    def reshow(self):
        self.show()
        self.raise_()
        self.activateWindow()


    def send(self, signalName, value, id=None):
        if not self.hasOutputName(signalName):
            print("Internal error: signal '%s' is not a valid signal name for"
                  "widget '%s'." % (signalName, self.captionTitle))
        if signalName in self.linksOut:
            self.linksOut[signalName][id] = value
        else:
            self.linksOut[signalName] = {id: value}

        if self.signalManager is not None:
            self.signalManager.send(self, signalName, value, id)

    def __setattr__(self, name, value):
        """Set value to members of this instance or any of its members.

        If member is used in a gui control, notify the control about the change.

        name: name of the member, dot is used for nesting ("graph.point.size").
        value: value to set to the member.

        """

        names = name.rsplit(".")
        field_name = names.pop()
        obj = reduce(lambda o, n: getattr(o, n, None), names, self)
        if obj is None:
            raise AttributeError("Cannot set '{}' to {} ".format(name, value))

        if obj is self:
            super().__setattr__(field_name, value)
        else:
            setattr(obj, field_name, value)

        notify_changed(obj, field_name, value)

        if self.settingsHandler:
            self.settingsHandler.fast_save(self, name, value)

    def openContext(self, *a):
        self.settingsHandler.open_context(self, *a)

    def closeContext(self):
        if self.current_context is not None:
            self.settingsHandler.close_context(self)
        self.current_context = None

    def retrieveSpecificSettings(self):
        pass

    def storeSpecificSettings(self):
        pass

    def saveSettings(self):
        self.settingsHandler.update_class_defaults(self)

    # this function is only intended for derived classes to send appropriate
    # signals when all settings are loaded
    def activateLoadedSettings(self):
        pass

    # reimplemented in other widgets
    def onDeleteWidget(self):
        pass

    def setOptions(self):
        pass

    def hasInputName(self, name):
        return any(signal.name == name for signal in self.inputs)

    def hasOutputName(self, name):
        return any(signal.name == name for signal in self.outputs)

    def getInputType(self, name):
        for signal in self.inputs:
            if signal.name == name:
                return signal

    def getOutputType(self, name):
        for signal in self.outputs:
            if signal.name == name:
                return signal

    def signalIsOnlySingleConnection(self, signalName):
        for input in self.inputs:
            if input.name == signalName:
                return input.single

    def addInputConnection(self, widgetFrom, signalName):
        for input in self.inputs:
            if input.name == signalName:
                handler = getattr(self, input.handler) # get a bound handler
                break
        else:
            raise ValueError("Widget {} has no signal {}".format(self.name,
                                                                 signalName))

        links = self.linksIn.setdefault(signalName, [])
        for _, widget, _, _ in links:
            if widget == widgetFrom:
                return # a signal from the same widget already exists
        links.append((0, widgetFrom, handler, []))

    # delete a link from widgetFrom and this widget with name signalName
    def removeInputConnection(self, widgetFrom, signalName):
        links = self.linksIn.get(signalName, [])
        for i, (_, widget, _, _) in enumerate(links):
            if widgetFrom == widget:
                del links[i]
                if not links:  # if key is empty, delete key value
                    del self.linksIn[signalName]
                return

    # return widget that is already connected to this singlelink signal.
    # If this widget exists, the connection will be deleted (since this is
    # only single connection link)
    def removeExistingSingleLink(self, signal):
        for input in self.inputs:
            if input.name == signal and not input.single:
                return None
        for signalName in self.linksIn.keys():
            if signalName == signal:
                widget = self.linksIn[signalName][0][1]
                del self.linksIn[signalName]
                return widget
        return None


    def handleNewSignals(self):
        # this is called after all new signals have been handled
        # implement this in your widget if you want to process something only
        # after you received multiple signals
        pass

    # signal manager calls this function when all input signals have updated
    # the data
    #noinspection PyBroadException
    def processSignals(self):
        if self.processingHandler:
            self.processingHandler(self, 1)    # focus on active widget
        newSignal = 0        # did we get any new signals

        # we define only handling signals that have defined a handler function
        for signal in self.inputs:  # we go from the first to the last input
            key = signal.name
            if key in self.linksIn:
                for i in range(len(self.linksIn[key])):
                    dirty, widgetFrom, handler, signalData = self.linksIn[key][i]
                    if not (handler and dirty):
                        continue
                    newSignal = 1
                    qApp.setOverrideCursor(Qt.WaitCursor)
                    try:
                        for (value, id, nameFrom) in signalData:
                            if self.signalIsOnlySingleConnection(key):
                                self.printEvent(
                                    "ProcessSignals: Calling %s with %s" %
                                    (handler, value), eventVerbosity=2)
                                handler(value)
                            else:
                                self.printEvent(
                                    "ProcessSignals: Calling %s with %s "
                                    "(%s, %s)" % (handler, value, nameFrom, id)
                                    , eventVerbosity=2)
                                handler(value, (widgetFrom, nameFrom, id))
                    except:
                        type, val, traceback = sys.exc_info()
                        # we pretend to have handled the exception, so that we
                        # don't crash other widgets
                        sys.excepthook(type, val, traceback)
                    qApp.restoreOverrideCursor()

                    # clear the dirty flag
                    self.linksIn[key][i] = (0, widgetFrom, handler, [])

        if newSignal == 1:
            self.handleNewSignals()

        while self.isBlocking():
            self.thread().msleep(50)
            qApp.processEvents()

        if self.processingHandler:
            self.processingHandler(self, 0)    # remove focus from this widget
        self.needProcessing = 0

    # set new data from widget widgetFrom for a signal with name signalName
    def updateNewSignalData(self, widgetFrom, signalName, value, id,
                            signalNameFrom):
        if signalName not in self.linksIn: return
        for i in range(len(self.linksIn[signalName])):
            (dirty, widget, handler, signalData) = self.linksIn[signalName][i]
            if widget == widgetFrom:
                if self.linksIn[signalName][i][3] == []:
                    self.linksIn[signalName][i] = \
                        (1, widget, handler, [(value, id, signalNameFrom)])
                else:
                    found = 0
                    for j in range(len(self.linksIn[signalName][i][3])):
                        (val, ID, nameFrom) = self.linksIn[signalName][i][3][j]
                        if ID == id and nameFrom == signalNameFrom:
                            self.linksIn[signalName][i][3][j] = \
                                (value, id, signalNameFrom)
                            found = 1
                    if not found:
                        self.linksIn[signalName][i] = \
                            (1, widget, handler, self.linksIn[signalName][i][3]
                                                 + [(value, id, signalNameFrom)])
        self.needProcessing = 1

    # ############################################
    # PROGRESS BAR FUNCTIONS

    def progressBarInit(self):
        self.progressBarValue = 0
        self.startTime = time.time()
        self.setWindowTitle(self.captionTitle + " (0% complete)")
        if self.progressBarHandler:
            self.progressBarHandler(self, 0)
        self.processingStateChanged.emit(1)

    def progressBarSet(self, value):
        if value > 0:
            self.__progressBarValue = value
            usedTime = max(1, time.time() - self.startTime)
            totalTime = (100.0 * usedTime) / float(value)
            remainingTime = max(0, totalTime - usedTime)
            h = int(remainingTime / 3600)
            min = int((remainingTime - h * 3600) / 60)
            sec = int(remainingTime - h * 3600 - min * 60)
            if h > 0:
                text = "%(h)d:%(min)02d:%(sec)02d" % vars()
            else:
                text = "%(min)d:%(sec)02d" % vars()
            self.setWindowTitle(self.captionTitle +
                                " (%(value).2f%% complete, remaining time: %(text)s)" % vars())
        else:
            self.setWindowTitle(self.captionTitle + " (0% complete)")
        if self.progressBarHandler:
            self.progressBarHandler(self, value)

        self.progressBarValueChanged.emit(value)

        qApp.processEvents()

    def progressBarValue(self):
        return self.__progressBarValue

    progressBarValue = pyqtProperty(float, fset=progressBarSet,
                                    fget=progressBarValue)

    def progressBarAdvance(self, value):
        self.progressBarSet(self.progressBarValue + value)

    def progressBarFinished(self):
        self.setWindowTitle(self.captionTitle)
        if self.progressBarHandler:
            self.progressBarHandler(self, 101)
        self.processingStateChanged.emit(0)

    # handler must accept two arguments: the widget instance and a value
    # between -1 and 101
    def setProgressBarHandler(self, handler):
        self.progressBarHandler = handler

    def setProcessingHandler(self, handler):
        self.processingHandler = handler

    def setEventHandler(self, handler):
        self.eventHandler = handler

    def setWidgetStateHandler(self, handler):
        self.widgetStateHandler = handler


    # if we are in debug mode print the event into the file
    def printEvent(self, text, eventVerbosity=1):
        self.signalManager.addEvent(self.captionTitle + ": " + text,
                                    eventVerbosity=eventVerbosity)
        if self.eventHandler:
            self.eventHandler(self.captionTitle + ": " + text, eventVerbosity)

    def openWidgetHelp(self):
        if "widgetInfo" in self.__dict__:  # This widget is on a canvas.
            qApp.canvasDlg.helpWindow.showHelpFor(self.widgetInfo, True)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Help, Qt.Key_F1):
            self.openWidgetHelp()
        #    e.ignore()
        elif (int(e.modifiers()), e.key()) in OWWidget.defaultKeyActions:
            OWWidget.defaultKeyActions[int(e.modifiers()), e.key()](self)
        else:
            QDialog.keyPressEvent(self, e)

    def information(self, id=0, text=None):
        self.setState("Info", id, text)
        #self.setState("Warning", id, text)

    def warning(self, id=0, text=""):
        self.setState("Warning", id, text)

    def error(self, id=0, text=""):
        self.setState("Error", id, text)

    def setState(self, stateType, id, text):
        changed = 0
        if type(id) == list:
            for val in id:
                if val in self.widgetState[stateType]:
                    self.widgetState[stateType].pop(val)
                    changed = 1
        else:
            if type(id) == str:
                text = id
                id = 0
            if not text:
                if id in self.widgetState[stateType]:
                    self.widgetState[stateType].pop(id)
                    changed = 1
            else:
                self.widgetState[stateType][id] = text
                changed = 1

        if changed:
            if self.widgetStateHandler:
                self.widgetStateHandler()
            elif text:
                self.printEvent(stateType + " - " + text)

            if type(id) == list:
                for i in id:
                    self.widgetStateChanged.emit(stateType, i, "")
            else:
                self.widgetStateChanged.emit(stateType, id, text or "")
        return changed

    def widgetStateToHtml(self, info=True, warning=True, error=True):
        pixmaps = self.getWidgetStateIcons()
        items = []
        iconPath = {"Info": "canvasIcons:information.png",
                    "Warning": "canvasIcons:warning.png",
                    "Error": "canvasIcons:error.png"}
        for show, what in [(info, "Info"), (warning, "Warning"),
                           (error, "Error")]:
            if show and self.widgetState[what]:
                items.append('<img src="%s" style="float: left;"> %s' %
                             (iconPath[what],
                              "\n".join(self.widgetState[what].values())))
        return "<br>".join(items)

    @classmethod
    def getWidgetStateIcons(cls):
        if not hasattr(cls, "_cached__widget_state_icons"):
            iconsDir = os.path.join(environ.canvas_install_dir, "icons")
            QDir.addSearchPath("canvasIcons",
                               os.path.join(environ.canvas_install_dir,
                                            "icons/"))
            info = QPixmap("canvasIcons:information.png")
            warning = QPixmap("canvasIcons:warning.png")
            error = QPixmap("canvasIcons:error.png")
            cls._cached__widget_state_icons = \
                {"Info": info, "Warning": warning, "Error": error}
        return cls._cached__widget_state_icons

    defaultKeyActions = {}

    if sys.platform == "darwin":
        defaultKeyActions = {
            (Qt.ControlModifier, Qt.Key_M):
                lambda self: self.showMaximized
                if self.isMinimized() else self.showMinimized(),
            (Qt.ControlModifier, Qt.Key_W):
                lambda self: self.setVisible(not self.isVisible())}


    def scheduleSignalProcessing(self):
        self.signalManager.scheduleSignalProcessing(self)

    def setBlocking(self, state=True):
        """ Set blocking flag for this widget. While this flag is set this
        widget and all its descendants will not receive any new signals from
        the signal manager
        """
        self.asyncBlock = state
        self.blockingStateChanged.emit(self.asyncBlock)
        if not self.isBlocking():
            self.scheduleSignalProcessing()


    def isBlocking(self):
        """ Is this widget blocking signal processing. Widget is blocking if
        asyncBlock value is True or any AsyncCall objects in asyncCalls list
        has blocking flag set
        """
        return self.asyncBlock or any(a.blocking for a in self.asyncCalls)

    def asyncExceptionHandler(self, exception):
        (etype, value, tb) = exception
        sys.excepthook(etype, value, tb)

    def asyncFinished(self, async, _):
        """ Remove async from asyncCalls, update blocking state
        """

        index = self.asyncCalls.index(async)
        async = self.asyncCalls.pop(index)

        if async.blocking and not self.isBlocking():
            # if we are responsible for unblocking
            self.blockingStateChanged.emit(False)
            self.scheduleSignalProcessing()

        async.disconnect(async, SIGNAL("finished(PyQt_PyObject, QString)"), self.asyncFinished)
        self.asyncCallsStateChange.emit()


    def asyncCall(self, func, args=(), kwargs={}, name=None,
                  onResult=None, onStarted=None, onFinished=None, onError=None,
                  blocking=True, thread=None, threadPool=None):
        """ Return an OWConcurent.AsyncCall object func, args and kwargs
        set and signals connected.
        """

        asList = lambda slot: slot if isinstance(slot, list) \
            else ([slot] if slot else [])

        onResult = asList(onResult)
        onStarted = asList(onStarted)
        onFinished = asList(onFinished)
        onError = asList(onError) or [self.asyncExceptionHandler]

        async = AsyncCall(func, args, kwargs,
                          thread=thread, threadPool=threadPool)
        async.name = name if name is not None else ""

        for slot in onResult:
            async.resultReady.connect(slot, Qt.QueuedConnection)
        for slot in onStarted:
            async.starting.connect(slot, Qt.QueuedConnection)
        for slot in onFinished:
            async.finished.connect(slot, Qt.QueuedConnection)
        for slot in onError:
            async.unhandledException.connect(slot, Qt.QueuedConnection)

        self.addAsyncCall(async, blocking)

        return async

    def addAsyncCall(self, async, blocking=True):
        """ Add AsyncCall object to asyncCalls list (will be removed
        once it finishes processing).

        """
        ## TODO: make this thread safe
        async.finished.connect(self.asyncFinished())

        async.blocking = blocking

        if blocking:
            # if we are responsible for blocking
            state = any(a.blocking for a in self.asyncCalls)
            self.asyncCalls.append(async)
            if not state:
                self.blockingStateChanged.emit(True)
        else:
            self.asyncCalls.append(async)

        self.asyncCallsStateChange.emit()


def blocking(method):
    """ Return method that sets blocking flag while executing
    """
    from functools import wraps

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        old = self._blocking
        self.setBlocking(True)
        try:
            return method(self, *args, **kwargs)
        finally:
            self.setBlocking(old)
