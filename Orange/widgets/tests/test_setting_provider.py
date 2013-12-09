import unittest
from Orange.widgets.settings import Setting, SettingProvider

SHOW_ZOOM_TOOLBAR = "show_zoom_toolbar"
SHOW_GRAPH = "show_graph"
GRAPH = "graph"
ZOOM_TOOLBAR = "zoom_toolbar"
SHOW_LABELS = "show_labels"
SHOW_X_AXIS = "show_x_axis"
SHOW_Y_AXIS = "show_y_axis"
ALLOW_ZOOMING = "allow_zooming"


def initialize_settings(instance):
    """This is usually done in Widget's new,
    but we avoid all that complications for tests."""
    provider = default_provider.get_provider(instance.__class__)
    if provider:
        provider.initialize(instance)
default_provider = None


class BaseGraph:
    show_labels = Setting(True)

    def __init__(self):
        initialize_settings(self)


class Graph(BaseGraph):
    show_x_axis = Setting(True)
    show_y_axis = Setting(True)

    def __init__(self):
        super().__init__()
        initialize_settings(self)


class ExtendedGraph(Graph):
    pass


class ZoomToolbar:
    allow_zooming = Setting(True)

    def __init__(self):
        initialize_settings(self)


class BaseWidget:
    settingsHandler = None

    show_graph = Setting(True)

    graph = SettingProvider(Graph)

    def __init__(self):
        initialize_settings(self)
        self.graph = Graph()


class Widget(BaseWidget):
    show_zoom_toolbar = Setting(True)

    zoom_toolbar = SettingProvider(ZoomToolbar)

    def __init__(self):
        super().__init__()
        initialize_settings(self)

        self.zoom_toolbar = ZoomToolbar()


class SettingProviderTestCase(unittest.TestCase):
    def setUp(self):
        global default_provider
        default_provider = SettingProvider(Widget)

    def tearDown(self):
        default_provider.settings[SHOW_GRAPH].default = True
        default_provider.settings[SHOW_ZOOM_TOOLBAR].default = True
        default_provider.providers[GRAPH].settings[SHOW_LABELS].default = True
        default_provider.providers[GRAPH].settings[SHOW_X_AXIS].default = True
        default_provider.providers[GRAPH].settings[SHOW_Y_AXIS].default = True
        default_provider.providers[ZOOM_TOOLBAR].settings[ALLOW_ZOOMING].default = True

    def test_registers_all_settings(self):
        self.assertDefaultSettingsEqual(default_provider, {
            GRAPH: {
                SHOW_LABELS: True,
                SHOW_X_AXIS: True,
                SHOW_Y_AXIS: True,
            },
            ZOOM_TOOLBAR: {
                ALLOW_ZOOMING: True,
            },
            SHOW_ZOOM_TOOLBAR: True,
            SHOW_GRAPH: True,
        })

    def test_sets_defaults(self):
        default_provider.set_defaults({
            SHOW_ZOOM_TOOLBAR: Setting(False),
            SHOW_GRAPH: Setting(False),
            GRAPH: {
                SHOW_LABELS: Setting(False),
                SHOW_X_AXIS: Setting(False),
            },
            ZOOM_TOOLBAR: {
                ALLOW_ZOOMING: Setting(False),
            }
        })

        self.assertDefaultSettingsEqual(default_provider, {
            GRAPH: {
                SHOW_LABELS: False,
                SHOW_X_AXIS: False,
                SHOW_Y_AXIS: True,
            },
            ZOOM_TOOLBAR: {
                ALLOW_ZOOMING: False,
            },
            SHOW_ZOOM_TOOLBAR: False,
            SHOW_GRAPH: False,
        })

    def test_gets_defaults(self):
        default_provider.settings[SHOW_GRAPH].default = False
        default_provider.providers[GRAPH].settings[SHOW_LABELS].default = False

        defaults = default_provider.get_defaults()

        self.assertEqual(defaults[SHOW_GRAPH].default, False)
        self.assertEqual(defaults[SHOW_ZOOM_TOOLBAR].default, True)
        self.assertEqual(defaults[GRAPH][SHOW_LABELS].default, False)
        self.assertEqual(defaults[GRAPH][SHOW_X_AXIS].default, True)
        self.assertEqual(defaults[GRAPH][SHOW_Y_AXIS].default, True)
        self.assertEqual(defaults[ZOOM_TOOLBAR][ALLOW_ZOOMING].default, True)

    def test_updates_defaults(self):
        widget = Widget()

        widget.show_graph = False
        widget.graph.show_y_axis = False

        default_provider.update_defaults(widget)

        self.assertDefaultSettingsEqual(default_provider, {
            GRAPH: {
                SHOW_LABELS: True,
                SHOW_X_AXIS: True,
                SHOW_Y_AXIS: False,
            },
            ZOOM_TOOLBAR: {
                ALLOW_ZOOMING: True,
            },
            SHOW_ZOOM_TOOLBAR: True,
            SHOW_GRAPH: False,
        })

    def test_initialize_sets_defaults(self):
        widget = Widget()

        self.assertEqual(widget.show_graph, True)
        self.assertEqual(widget.show_zoom_toolbar, True)
        self.assertEqual(widget.graph.show_labels, True)
        self.assertEqual(widget.graph.show_x_axis, True)
        self.assertEqual(widget.graph.show_y_axis, True)
        self.assertEqual(widget.zoom_toolbar.allow_zooming, True)

    def test_initialize_with_data_sets_values_from_data(self):
        widget = Widget()
        default_provider.initialize(widget, {
            SHOW_GRAPH: False,
            GRAPH: {
                SHOW_Y_AXIS: False
            }
        })

        self.assertEqual(widget.show_graph, False)
        self.assertEqual(widget.show_zoom_toolbar, True)
        self.assertEqual(widget.graph.show_labels, True)
        self.assertEqual(widget.graph.show_x_axis, True)
        self.assertEqual(widget.graph.show_y_axis, False)
        self.assertEqual(widget.zoom_toolbar.allow_zooming, True)

    def test_initialize_with_data_stores_initial_values_until_instance_is_connected(self):
        widget = Widget.__new__(Widget)

        default_provider.initialize(widget, {
            SHOW_GRAPH: False,
            GRAPH: {
                SHOW_Y_AXIS: False
            }
        })

        self.assertFalse(hasattr(widget.graph, SHOW_Y_AXIS))
        widget.graph = Graph()
        self.assertEqual(widget.graph.show_y_axis, False)

    def test_get_provider(self):
        self.assertEqual(default_provider.get_provider(BaseWidget), None)
        self.assertEqual(default_provider.get_provider(Widget), default_provider)
        self.assertEqual(default_provider.get_provider(BaseGraph), None)
        self.assertEqual(default_provider.get_provider(Graph), default_provider.providers[GRAPH])
        self.assertEqual(default_provider.get_provider(ExtendedGraph), default_provider.providers[GRAPH])
        self.assertEqual(default_provider.get_provider(ZoomToolbar), default_provider.providers[ZOOM_TOOLBAR])

    def test_pack_settings(self):
        widget = Widget()

        widget.show_graph = False
        widget.graph.show_y_axis = False

        packed_settings = default_provider.pack(widget)

        self.assertEqual(packed_settings, {
            SHOW_GRAPH: False,
            SHOW_ZOOM_TOOLBAR: True,
            GRAPH: {
                SHOW_LABELS: True,
                SHOW_X_AXIS: True,
                SHOW_Y_AXIS: False,
            },
            ZOOM_TOOLBAR: {
                ALLOW_ZOOMING: True,
            },
        })

    def test_unpack_settings(self):
        widget = Widget()
        default_provider.unpack(widget, {
            SHOW_GRAPH: False,
            GRAPH: {
                SHOW_Y_AXIS: False,
            },

        })

        self.assertEqual(widget.show_graph, False)
        self.assertEqual(widget.show_zoom_toolbar, True)
        self.assertEqual(widget.graph.show_labels, True)
        self.assertEqual(widget.graph.show_x_axis, True)
        self.assertEqual(widget.graph.show_y_axis, False)
        self.assertEqual(widget.zoom_toolbar.allow_zooming, True)

    def test_for_each_settings_works_without_instance_or_data(self):
        settings = set()

        def on_setting(setting, data, instance):
            settings.add(setting.name)

        default_provider.for_each_setting(on_setting=on_setting)
        self.assertEqual(settings, {
            SHOW_ZOOM_TOOLBAR, SHOW_GRAPH,
            SHOW_LABELS, SHOW_X_AXIS, SHOW_Y_AXIS,
            ALLOW_ZOOMING})

    def test_for_each_setting_selects_correct_data(self):
        settings = {}
        graph_data = {SHOW_LABELS: 3, SHOW_X_AXIS: 4, SHOW_Y_AXIS: 5}
        zoom_data = {ALLOW_ZOOMING: 6}
        data = {SHOW_GRAPH: 1, SHOW_ZOOM_TOOLBAR: 2,
                GRAPH: graph_data, ZOOM_TOOLBAR: zoom_data}

        def on_setting(setting, data, instance):
            settings[setting.name] = data

        default_provider.for_each_setting(
            data=data,
            on_setting=on_setting)

        self.assertEqual(
            settings,
            {
                SHOW_GRAPH: data,
                SHOW_ZOOM_TOOLBAR: data,
                SHOW_LABELS: graph_data,
                SHOW_X_AXIS: graph_data,
                SHOW_Y_AXIS: graph_data,
                ALLOW_ZOOMING: zoom_data,
            }
        )

    def test_for_each_setting_with_partial_data(self):
        settings = {}
        graph_data = {SHOW_LABELS: 3, SHOW_X_AXIS: 4}
        data = {SHOW_GRAPH: 1, SHOW_ZOOM_TOOLBAR: 2, GRAPH: graph_data}

        def on_setting(setting, data, instance):
            settings[setting.name] = data

        default_provider.for_each_setting(
            data=data,
            on_setting=on_setting)

        self.assertEqual(
            settings,
            {
                SHOW_GRAPH: data,
                SHOW_ZOOM_TOOLBAR: data,
                SHOW_LABELS: graph_data,
                SHOW_X_AXIS: graph_data,
                SHOW_Y_AXIS: graph_data,
                ALLOW_ZOOMING: {},
            }
        )

    def test_for_each_setting_selects_correct_instance(self):
        settings = {}
        widget = Widget()

        def on_setting(setting, data, instance):
            settings[setting.name] = instance

        default_provider.for_each_setting(
            instance=widget,
            on_setting=on_setting)

        self.assertEqual(
            settings,
            {
                SHOW_GRAPH: widget,
                SHOW_ZOOM_TOOLBAR: widget,
                SHOW_LABELS: widget.graph,
                SHOW_X_AXIS: widget.graph,
                SHOW_Y_AXIS: widget.graph,
                ALLOW_ZOOMING: widget.zoom_toolbar,
            }
        )

    def test_for_each_setting_with_partial_instance(self):
        settings = {}
        widget = Widget()
        widget.graph = None

        def on_setting(setting, data, instance):
            settings[setting.name] = instance

        default_provider.for_each_setting(
            instance=widget,
            on_setting=on_setting)

        self.assertEqual(
            settings,
            {
                SHOW_GRAPH: widget,
                SHOW_ZOOM_TOOLBAR: widget,
                SHOW_LABELS: None,
                SHOW_X_AXIS: None,
                SHOW_Y_AXIS: None,
                ALLOW_ZOOMING: widget.zoom_toolbar,
            }
        )

    def assertDefaultSettingsEqual(self, provider, defaults):
        for name, value in defaults.items():
            if isinstance(value, dict):
                self.assertIn(name, provider.providers)
                self.assertDefaultSettingsEqual(provider.providers[name], value)
            else:
                self.assertEqual(provider.settings[name].default, value)

if __name__ == '__main__':
    unittest.main(verbosity=2)
