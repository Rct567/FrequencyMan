"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from abc import ABC, abstractmethod
from typing import Optional, Union
from anki.collection import Collection

from aqt import QComboBox, QTableWidget, QTableWidgetItem
from aqt.qt import QVBoxLayout, QLabel, QSpacerItem, QSizePolicy, QWidget, QColor, QPalette, QLayout, QPaintEvent, QTextEdit, pyqtSlot, QTimer
from aqt.main import AnkiQt
from aqt.utils import showInfo, askUser, showWarning

from ..target_corpus_data import TargetCorpusData, SegmentContentMetrics, CorpusSegmentId
from ..target_list import TargetList
from ..target import Target


from .main_window import FrequencyManMainWindow, FrequencyManTab

from ..lib.utilities import var_dump_log, override


class NumericTableWidgetItem(QTableWidgetItem):
    def __init__(self, number: float):
        super().__init__(str(number))
        self._numeric_value = float(number)

    @override
    def __lt__(self, other: QTableWidgetItem) -> bool:
        if not isinstance(other, NumericTableWidgetItem):
            return super().__lt__(other)
        return self._numeric_value < other._numeric_value


class WordsOverviewOption(ABC):

    title: str
    selected_target: Target
    selected_corpus_segment_id: CorpusSegmentId
    selected_corpus_content_metrics: SegmentContentMetrics

    def __init__(self, selected_target: Target, selected_corpus_segment_id: CorpusSegmentId, selected_corpus_content_metrics: SegmentContentMetrics):
        self.selected_target = selected_target
        self.selected_corpus_segment_id = selected_corpus_segment_id
        self.selected_corpus_content_metrics = selected_corpus_content_metrics

    @abstractmethod
    def data_description(self) -> str:
        pass

    @abstractmethod
    def data(self) -> list[tuple[Union[str, float, int], ...]]:
        pass

    @abstractmethod
    def labels(self) -> list[str]:
        pass


class WordFamiliarityOverview(WordsOverviewOption):

    title = "Word familiarity"

    @override
    def data_description(self) -> str:
        return "Word familiarity for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> list[tuple[str, float]]:
        return [(str(word), familiarity) for word, familiarity in self.selected_corpus_content_metrics.words_familiarity.items()]

    @override
    def labels(self) -> list[str]:
        return ["Word", "Familiarity"]


class WordFrequencyOverview(WordsOverviewOption):

    title = "Word frequency"

    @override
    def data_description(self) -> str:
        return "Word frequency for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> list[tuple[str, float]]:
        return [(str(word), frequency) for word, frequency in self.selected_corpus_content_metrics.word_frequency.items()]

    @override
    def labels(self) -> list[str]:
        return ["Word", "Word frequency"]


class WordUnderexposureOverview(WordsOverviewOption):

    title = "Word underexposure"

    @override
    def data_description(self) -> str:
        return "Word underexposure for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> list[tuple[str, float]]:
        return [(str(word), underexposure) for word, underexposure in self.selected_corpus_content_metrics.words_underexposure.items()]

    @override
    def labels(self) -> list[str]:
        return ["Word", "Underexposure"]

class WordFamiliaritySweetspotOverview(WordsOverviewOption):

    title = "Word familiarity sweetspot"

    @override
    def data_description(self) -> str:
        return "Word familiarity sweetspot for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> list[tuple[str, float]]:
        return [(str(word), sweetspot) for word, sweetspot in self.selected_corpus_content_metrics.words_familiarity_sweetspot.items()]

    @override
    def labels(self) -> list[str]:
        return ["Word", "Sweetspot score"]

class MatureWordsOverview(WordsOverviewOption):

    title = "Mature words"

    @override
    def data_description(self) -> str:
        return "Mature words for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> list[tuple[str, float]]:
        return [(str(word), familiarity) for word, familiarity in self.selected_corpus_content_metrics.words_familiarity.items() if word in self.selected_corpus_content_metrics.mature_words]

    @override
    def labels(self) -> list[str]:
        return ["Word", "Familiarity"]

class NotInWordFrequencyListsOverview(WordsOverviewOption):

    title = "Not in word frequency lists"

    @override
    def data_description(self) -> str:
        return "Words not in word frequency lists for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> list[tuple]:

        no_fr_words = set(word for word in self.selected_corpus_content_metrics.all_words if word not in self.selected_corpus_content_metrics.word_frequency)
        num_cards = {word: len(cards) for word, cards in self.selected_corpus_content_metrics.cards_per_word.items() if word in no_fr_words}
        data: list[tuple[str, int]] = []

        for word in no_fr_words:
            word_num_cards = num_cards[word]
            data.append((str(word), word_num_cards))

        data = sorted(data, key=lambda x: x[1], reverse=True)

        return data

    @override
    def labels(self) -> list[str]:
        return ["Word", "Number of cards"]

class NotInTargetCardsOverview(WordsOverviewOption):

    title = "Not in target cards"

    @override
    def data_description(self) -> str:
        return "Words not in target cards for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> list[tuple]:

        self.selected_corpus_content_metrics.language_data.load_data({self.selected_corpus_content_metrics.lang_data_id})

        if self.selected_corpus_content_metrics.language_data.word_frequency_lists.word_frequency_lists is None:
            showWarning("No word frequency lists loaded.")
            return []

        words_in_frequency_lists = self.selected_corpus_content_metrics.language_data.word_frequency_lists.word_frequency_lists[self.selected_corpus_content_metrics.lang_data_id].keys()
        words_in_frequency_lists_with_position = {word: position+1 for position, word in enumerate(words_in_frequency_lists)}

        words_without_cards = [(word, position) for word, position in words_in_frequency_lists_with_position.items() if word not in self.selected_corpus_content_metrics.all_words]

        words_without_cards = sorted(words_without_cards, key=lambda x: x[1], reverse=False)

        return words_without_cards

    @override
    def labels(self) -> list[str]:
        return ["Word", "Word frequency list position"]


class WordsOverviewTab(FrequencyManTab):

    target_list: TargetList
    selected_target_index: int
    target_corpus_segment_dropdown: QComboBox
    overview_options: list[type[WordsOverviewOption]] = [
        WordFamiliarityOverview,
        WordFrequencyOverview,
        WordUnderexposureOverview,
        WordFamiliaritySweetspotOverview,
        MatureWordsOverview,
        NotInWordFrequencyListsOverview,
        NotInTargetCardsOverview
    ]
    overview_options_available: list[WordsOverviewOption]
    table_label: QLabel
    table: QTableWidget

    def __init__(self, fm_window: FrequencyManMainWindow, col: Collection) -> None:
        super().__init__(fm_window, col)
        self.id = 'words_overview'
        self.name = 'Words overview'
        self.selected_target_index = 0
        self.selected_overview_option_index = 0

    @override
    def on_tab_painted(self, tab_layout: QLayout) -> None:

        self.target_list = self.init_new_target_list()

        if 'reorder_target_list' not in self.fm_window.fm_config:
            showWarning("Error loading target list: 'reorder_target_list' is not defined.")
            return

        defined_target_list = self.fm_window.fm_config['reorder_target_list']

        try:
            self.target_list.set_targets_from_json(defined_target_list)
        except Exception as e:
            showWarning("Error loading target list: "+str(e))
            return

        # Target selection

        label = QLabel("Target:")
        tab_layout.addWidget(label)

        targets_dropdown = QComboBox()
        targets_dropdown.addItems([target.name for target in self.target_list])
        targets_dropdown.currentIndexChanged.connect(self.__set_selected_target)
        tab_layout.addWidget(targets_dropdown)

        # Target corpus segment selection

        label = QLabel("Target corpus segment:")
        label.setStyleSheet("margin-top:8px;")
        tab_layout.addWidget(label)
        self.target_corpus_segment_dropdown = QComboBox()
        self.target_corpus_segment_dropdown.currentIndexChanged.connect(self.__set_selected_target_corpus_segment)
        tab_layout.addWidget(self.target_corpus_segment_dropdown)

        # Overview options

        label = QLabel("Overview option:")
        label.setStyleSheet("margin-top:8px;")
        tab_layout.addWidget(label)
        self.overview_options_dropdown = QComboBox()
        self.overview_options_dropdown.addItems([option.title for option in self.overview_options])
        self.overview_options_dropdown.currentIndexChanged.connect(self.__set_selected_overview_option)
        tab_layout.addWidget(self.overview_options_dropdown)

        # table
        self.table_label = QLabel("")
        self.table_label.setStyleSheet("margin-top:8px;")
        tab_layout.addWidget(self.table_label)
        self.table = QTableWidget()
        tab_layout.addWidget(self.table)

        # Set first target as default
        QTimer.singleShot(1, lambda: self.__set_selected_target(0))

    def __get_selected_target(self) -> Target:
        return self.target_list[self.selected_target_index]

    def __get_selected_target_corpus_data(self) -> TargetCorpusData:
        selected_target = self.__get_selected_target()
        return selected_target.get_corpus_data(selected_target.get_cards())

    def __set_selected_target(self, index: int) -> None:
        self.selected_target_index = index
        selected_target_corpus_data = self.__get_selected_target_corpus_data()
        self.target_corpus_segment_dropdown.clear()
        self.target_corpus_segment_dropdown.addItems([segment_id for segment_id in selected_target_corpus_data.segments_ids])

    def __set_selected_target_corpus_segment(self, index: int) -> None:

        selected_target = self.__get_selected_target()
        target_corpus_data = self.__get_selected_target_corpus_data()
        selected_corpus_segment_id = list(target_corpus_data.segments_ids)[index]
        content_metrics = target_corpus_data.content_metrics[selected_corpus_segment_id]

        self.overview_options_available = [option(selected_target, selected_corpus_segment_id, content_metrics) for option in self.overview_options]

        self.__set_selected_overview_option(self.selected_overview_option_index)

    def __set_selected_overview_option(self, index: int) -> None:
        self.selected_overview_option_index = index
        selected_overview_option = self.overview_options_available[self.selected_overview_option_index]
        self.update_table(selected_overview_option)

    def update_table(self, overview_options: WordsOverviewOption) -> None:

        self.table_label.setText(overview_options.data_description())

        self.table.setDisabled(True)
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)

        data = overview_options.data()
        labels = overview_options.labels()

        self.table.clearContents()
        self.table.setRowCount(len(data))
        self.table.setColumnCount(len(labels))
        self.table.setHorizontalHeaderLabels(labels)

        # Populate the table
        for row_index, row_data in enumerate(data):
            for col_index, value in enumerate(row_data):
                if isinstance(value, float) or isinstance(value, int):
                    self.table.setItem(row_index, col_index, NumericTableWidgetItem(value))
                else:
                    self.table.setItem(row_index, col_index, QTableWidgetItem(str(value)))

        # Configure table header
        horizontal_header = self.table.horizontalHeader()
        if horizontal_header is not None:
            horizontal_header.setStretchLastSection(True)
            for col_index in range(len(labels)):
                horizontal_header.setSectionResizeMode(
                    col_index, horizontal_header.ResizeMode.Stretch
                )

        # Allow sorting and updates again
        self.table.setSortingEnabled(True)
        self.table.setUpdatesEnabled(True)
        self.table.setDisabled(False)
