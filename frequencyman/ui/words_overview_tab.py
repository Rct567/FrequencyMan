"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from abc import ABC, abstractmethod
from typing import Optional, Union
from anki.collection import Collection

from aqt import QComboBox, QTableWidget, QTableWidgetItem, QCheckBox
from aqt.qt import (
    QVBoxLayout, QLabel, QSpacerItem, QSizePolicy, QWidget, QColor,
    QPalette, QLayout, QPaintEvent, QTextEdit, pyqtSlot, QTimer,
    QHBoxLayout, QFrame
)
from aqt.main import AnkiQt
from aqt.utils import showInfo, askUser, showWarning

from ..text_processing import WordToken
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
    def data(self) -> list[tuple[Union[WordToken, float, int], ...]]:
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
    def data(self) -> list[tuple[WordToken, float]]:
        return [(word, familiarity) for word, familiarity in self.selected_corpus_content_metrics.words_familiarity.items()]

    @override
    def labels(self) -> list[str]:
        return ["Word", "Familiarity"]


class WordFrequencyOverview(WordsOverviewOption):

    title = "Word frequency"

    @override
    def data_description(self) -> str:
        return "Word frequency for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> list[tuple[WordToken, float]]:
        return [(word, frequency) for word, frequency in self.selected_corpus_content_metrics.word_frequency.items()]

    @override
    def labels(self) -> list[str]:
        return ["Word", "Word frequency"]


class WordUnderexposureOverview(WordsOverviewOption):

    title = "Word underexposure"

    @override
    def data_description(self) -> str:
        return "Word underexposure for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> list[tuple[WordToken, float]]:
        return [(word, underexposure) for word, underexposure in self.selected_corpus_content_metrics.words_underexposure.items()]

    @override
    def labels(self) -> list[str]:
        return ["Word", "Underexposure"]

class WordFamiliaritySweetspotOverview(WordsOverviewOption):

    title = "Word familiarity sweetspot"

    @override
    def data_description(self) -> str:
        return "Word familiarity sweetspot for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> list[tuple[WordToken, float]]:
        return [(word, sweetspot) for word, sweetspot in self.selected_corpus_content_metrics.words_familiarity_sweetspot.items()]

    @override
    def labels(self) -> list[str]:
        return ["Word", "Sweetspot score"]

class MatureWordsOverview(WordsOverviewOption):

    title = "Mature words"

    @override
    def data_description(self) -> str:
        return "Mature words for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> list[tuple[WordToken, float]]:
        return [(word, familiarity) for word, familiarity in self.selected_corpus_content_metrics.words_familiarity.items() if word in self.selected_corpus_content_metrics.mature_words]

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

class LonelyWordsOverview(WordsOverviewOption):

    title = "Lonely words"

    @override
    def data_description(self) -> str:
        return "Lonely words (words with only one note) for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> list[tuple[WordToken, float]]:

        num_notes = {word: len(set(card.nid for card in cards)) for word, cards in self.selected_corpus_content_metrics.cards_per_word.items()}
        lonely_words = set(word for word, num_notes in num_notes.items() if num_notes == 1)

        data = [(word, self.selected_corpus_content_metrics.words_familiarity.get(word, 0.0)) for word in lonely_words]
        data = sorted(data, key=lambda x: x[1], reverse=True)
        return data

    @override
    def labels(self) -> list[str]:
        return ["Word", "Familiarity"]


class WordPresenceOverview(WordsOverviewOption):

    title = "Word presence"

    @override
    def data_description(self) -> str:
        return "Word presence for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> list[tuple[WordToken, float]]:

        word_presence_scores = {word: max(presence) for word, presence in self.selected_corpus_content_metrics.all_words_presence.items()}

        data = [(word, presence) for word, presence in word_presence_scores.items()]
        data = sorted(data, key=lambda x: x[1], reverse=True)

        return data

    @override
    def labels(self) -> list[str]:
        return ["Word", "Presence score"]


class NewWordsOverview(WordsOverviewOption):

    title = "New words"

    @override
    def data_description(self) -> str:
        return "New words (words not yet reviewed) for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> list[tuple[WordToken, float, int]]:

        new_words = self.selected_corpus_content_metrics.new_words
        new_words_num_notes = {word: len(set(card.nid for card in cards)) for word, cards in self.selected_corpus_content_metrics.cards_per_word.items() if word in new_words}

        data = [(word, self.selected_corpus_content_metrics.word_frequency.get(word, 0.0), new_words_num_notes[word]) for word in new_words]
        data = sorted(data, key=lambda x: x[1], reverse=True)
        return data

    @override
    def labels(self) -> list[str]:
        return ["Word", "Word frequency", "Number of notes"]


class FocusWordsOverview(WordsOverviewOption):

    title = "Focus words"

    @override
    def data_description(self) -> str:
        return "Focus words for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> list[tuple[WordToken, float, float]]:

        focus_words = {word for word in self.selected_corpus_content_metrics.all_words if word not in self.selected_corpus_content_metrics.mature_words}
        focus_words_frequency = {word: self.selected_corpus_content_metrics.word_frequency.get(word, 0.0) for word in focus_words}
        focus_words_familiarity = {word: self.selected_corpus_content_metrics.words_familiarity.get(word, 0.0) for word in focus_words}

        data = [(word, focus_words_frequency[word], focus_words_familiarity[word]) for word in focus_words]
        data = sorted(data, key=lambda x: x[1], reverse=True)
        return data

    @override
    def labels(self) -> list[str]:
        return ["Word", "Word frequency", "Familiarity"]


class AdditionalColumn(ABC):

    title: str

    @abstractmethod
    def get_values(self, words: list[WordToken], metrics: SegmentContentMetrics) -> list[Union[float, int, str]]:
        pass

    def should_hide(self, current_labels: list[str]) -> bool:
        return self.title in current_labels


class WordFrequencyColumn(AdditionalColumn):

    title = "Word frequency"

    @override
    def get_values(self, words: list[WordToken], metrics: SegmentContentMetrics) -> list[Union[float, int, str]]:
        return [metrics.word_frequency.get(word, 0.0) for word in words]


class WordFamiliarityColumn(AdditionalColumn):

    title = "Familiarity"

    @override
    def get_values(self, words: list[WordToken], metrics: SegmentContentMetrics) -> list[Union[float, int, str]]:
        return [metrics.words_familiarity.get(word, 0.0) for word in words]


class NumberOfCardsColumn(AdditionalColumn):

    title = "Number of cards"

    @override
    def get_values(self, words: list[WordToken], metrics: SegmentContentMetrics) -> list[Union[float, int, str]]:
        return [len(set(card.id for card in metrics.cards_per_word.get(word, []))) for word in words]

class NumberOfNotesColumn(AdditionalColumn):

    title = "Number of notes"

    @override
    def get_values(self, words: list[WordToken], metrics: SegmentContentMetrics) -> list[Union[float, int, str]]:
        return [len(set(card.nid for card in metrics.cards_per_word.get(word, []))) for word in words]


class WordsOverviewTab(FrequencyManTab):

    target_list: TargetList
    selected_target_index: int
    target_corpus_segment_dropdown: QComboBox
    overview_options: list[type[WordsOverviewOption]] = [
        WordFamiliarityOverview,
        WordFrequencyOverview,
        WordUnderexposureOverview,
        WordFamiliaritySweetspotOverview,
        WordPresenceOverview,
        NewWordsOverview,
        FocusWordsOverview,
        MatureWordsOverview,
        LonelyWordsOverview,
        NotInWordFrequencyListsOverview,
        NotInTargetCardsOverview,
    ]
    overview_options_available: list[WordsOverviewOption]
    table_label: QLabel
    table: QTableWidget

    additional_columns: list[AdditionalColumn]
    additional_column_checkboxes: dict[str, QCheckBox]

    def __init__(self, fm_window: FrequencyManMainWindow, col: Collection) -> None:
        super().__init__(fm_window, col)
        self.id = 'words_overview'
        self.name = 'Words overview'
        self.selected_target_index = 0
        self.selected_overview_option_index = 0
        self.additional_columns = [
            WordFrequencyColumn(),
            WordFamiliarityColumn(),
            NumberOfCardsColumn(),
            NumberOfNotesColumn()
        ]
        self.additional_column_checkboxes = {}

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

        # Table
        self.table_label = QLabel("")
        self.table_label.setStyleSheet("margin-top:8px;")
        tab_layout.addWidget(self.table_label)
        self.table = QTableWidget()
        tab_layout.addWidget(self.table)

        # Additional columns options
        additional_columns_frame = QFrame()
        additional_columns_layout = QHBoxLayout()
        additional_columns_layout.setContentsMargins(0, 0, 0, 0)
        additional_columns_frame.setLayout(additional_columns_layout)

        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        additional_columns_layout.addItem(spacer)

        for column in self.additional_columns:
            checkbox = QCheckBox(column.title)
            checkbox.stateChanged.connect(self.update_table)
            self.additional_column_checkboxes[column.title] = checkbox
            additional_columns_layout.addWidget(checkbox)

        tab_layout.addWidget(additional_columns_frame)

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
        self.update_table()

    def update_table(self) -> None:

        overview_options = self.overview_options_available[self.selected_overview_option_index]

        self.table_label.setText(overview_options.data_description())

        self.table.setDisabled(True)
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)

        data = overview_options.data()
        labels = overview_options.labels()

        # Update visibility of checkboxes based on current labels
        for column in self.additional_columns:
            checkbox = self.additional_column_checkboxes[column.title]
            checkbox.setVisible(not column.should_hide(labels))

        # Add additional columns if checked
        additional_labels: list[str] = []
        additional_data: dict[str, list[Union[float, int, str]]] = {}

        for column in self.additional_columns:
            checkbox = self.additional_column_checkboxes[column.title]
            if checkbox.isChecked() and not column.should_hide(labels):
                additional_column_values = column.get_values([row_data[0] for row_data in data if isinstance(row_data[0], str)], overview_options.selected_corpus_content_metrics)

                if len(additional_column_values) != len(data):
                    raise Exception("Number of rows for additional column does not match the number of rows already in table.")

                additional_labels.append(column.title)
                additional_data[column.title] = additional_column_values


        # Set up table with combined columns
        combined_labels = labels + additional_labels
        self.table.clearContents()
        self.table.setRowCount(len(data))
        self.table.setColumnCount(len(combined_labels))
        self.table.setHorizontalHeaderLabels(combined_labels)

        # Populate the table
        for row_index, row_data in enumerate(data):
            # Original columns
            for col_index, value in enumerate(row_data):
                if isinstance(value, (float, int)):
                    self.table.setItem(row_index, col_index, NumericTableWidgetItem(value))
                else:
                    self.table.setItem(row_index, col_index, QTableWidgetItem(str(value)))

            # Additional columns
            for col_index, column_title in enumerate(additional_labels, start=len(labels)):
                value = additional_data[column_title][row_index]
                if isinstance(value, (float, int)):
                    self.table.setItem(row_index, col_index, NumericTableWidgetItem(value))
                else:
                    self.table.setItem(row_index, col_index, QTableWidgetItem(str(value)))

        # Configure table header
        horizontal_header = self.table.horizontalHeader()
        if horizontal_header is not None:
            horizontal_header.setStretchLastSection(True)
            for col_index in range(len(combined_labels)):
                horizontal_header.setSectionResizeMode(
                    col_index, horizontal_header.ResizeMode.Stretch
                )

        # Allow sorting and updates again
        self.table.setSortingEnabled(True)
        self.table.setUpdatesEnabled(True)
        self.table.setDisabled(False)
