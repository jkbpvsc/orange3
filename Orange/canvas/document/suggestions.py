import os
import pickle
from collections import defaultdict

from Orange.canvas import config


class Suggestions:
    def __init__(self):
        self.__frequencies_path = config.data_dir() + "widget-use-frequency.p"

        self.__scheme = None
        self.link_frequencies = defaultdict(int)
        self.source_probability = defaultdict(lambda: defaultdict(float))
        self.sink_probability = defaultdict(lambda: defaultdict(float))

        if not self.load_link_frequency():
            self.default_link_frequency()

    def load_link_frequency(self):
        if not os.path.isfile(self.__frequencies_path):
            return False
        file = open(self.__frequencies_path, "rb")
        self.link_frequencies = pickle.load(file)

        self.overwrite_probabilities_with_frequencies()
        return True

    def default_link_frequency(self):
        self.link_frequencies[("File", "Data Table")] = 3
        self.overwrite_probabilities_with_frequencies()

    def overwrite_probabilities_with_frequencies(self):
        for link, count in self.link_frequencies.items():
            self.source_probability[link[0]][link[1]] = count
            self.sink_probability[link[1]][link[0]] = count

    def write_link_frequency(self):
        pickle.dump(self.link_frequencies, open(self.__frequencies_path, "wb"))

    def new_link(self, link):
        source_id = link.source_node.description.name
        sink_id = link.sink_node.description.name

        link_key = (source_id, sink_id)
        self.link_frequencies[link_key] += 1

        self.source_probability[source_id][sink_id] += 1
        self.sink_probability[sink_id][source_id] += 1

        self.write_link_frequency()

    def get_sink_suggestions(self, source_id):
        return self.source_probability[source_id]

    def get_source_suggestions(self, sink_id):
        return self.sink_probability[sink_id]

    def set_scheme(self, scheme):
        self.__scheme = scheme
        scheme.onNewLink(self.new_link)