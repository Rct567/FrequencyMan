"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from typing import Optional, Union
from anki.collection import Collection

from aqt import QColor, QComboBox, QCursor, QKeyEvent, QKeySequence, QMenu, QPoint, QTableWidget, QTableWidgetItem, QCheckBox, dialogs
from aqt.qt import (
    QLabel, QSpacerItem, QSizePolicy, QLayout, QTimer, QHBoxLayout, QFrame, Qt, QApplication
)
from aqt.utils import showInfo, askUser, showWarning
from aqt.browser.browser import Browser

from ..target_corpus_data import SegmentContentMetrics, TargetCorpusData, CorpusSegmentId
from ..target_list import TargetList
from ..target import Target

from .words_overview_tab_additional_columns import (
    AdditionalColumn, WordFrequencyColumn, WordFamiliarityColumn, NumberOfCardsColumn, NumberOfNotesColumn, WordPresenceColumn)
from .words_overview_tab_overview_options import (
    AllWordsOverview, LearningWordsOverview, MatureWordsOverview, WordsOverviewOption, WordFamiliarityOverview, WordFrequencyOverview, WordUnderexposureOverview,
    WordFamiliaritySweetspotOverview, NotInWordFrequencyListsOverview,
    NotInTargetCardsOverview, LonelyWordsOverview, NewWordsOverview, FocusWordsOverview)
from .words_overview_filters import FilterOption, LearningWordsFilter, MatureWordsFilter

from .main_window import FrequencyManMainWindow, FrequencyManTab

from ..lib.utilities import batched, var_dump_log, override
from ..text_processing import WordToken


class NumericTableWidgetItem(QTableWidgetItem):
    def __init__(self, number: float):
        super().__init__(str(number))
        self._numeric_value = float(number)

    @override
    def __lt__(self, other: QTableWidgetItem) -> bool:
        if not isinstance(other, NumericTableWidgetItem):
            return super().__lt__(other)
        return self._numeric_value < other._numeric_value


class WordsOverviewTab(FrequencyManTab):

    target_list: TargetList
    selected_target_index: int
    selected_corpus_segment_id: CorpusSegmentId
    target_corpus_segment_dropdown: QComboBox
    overview_options: list[type[WordsOverviewOption]] = [
        WordFamiliarityOverview,
        WordFrequencyOverview,
        WordUnderexposureOverview,
        WordFamiliaritySweetspotOverview,
        NewWordsOverview,
        AllWordsOverview,
        FocusWordsOverview,
        LearningWordsOverview,
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

    filters: list[FilterOption]
    filter_checkboxes: dict[str, QCheckBox]

    def __init__(self, fm_window: FrequencyManMainWindow, col: Collection) -> None:
        super().__init__(fm_window, col)
        self.id = 'words_overview'
        self.name = 'Words overview'
        self.selected_target_index = 0
        self.selected_overview_option_index = 0
        self.additional_columns = [
            WordFrequencyColumn(),
            WordFamiliarityColumn(),
            WordPresenceColumn(),
            NumberOfCardsColumn(),
            NumberOfNotesColumn()
        ]
        self.additional_column_checkboxes = {}
        self.filters = [
            LearningWordsFilter(),
            MatureWordsFilter()
        ]
        self.filter_checkboxes = {}

    def __load_target_list(self) -> None:

        self.target_list = self.init_new_target_list()

        if 'reorder_target_list' not in self.fm_window.fm_config:
            raise Exception("'reorder_target_list' is not defined.")

        defined_target_list = self.fm_window.fm_config['reorder_target_list']
        self.target_list.set_targets_from_json(defined_target_list)

    @override
    def on_tab_focus(self, tab_layout: QLayout) -> None:

        self.clear_layout(tab_layout)
        self.__init_words_overview(tab_layout)

    def __init_words_overview(self, tab_layout: QLayout) -> None:

        try:
            self.__load_target_list()
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
        self.table.keyPressEvent = self.__handle_key_press

        # Add context menu to table
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.__show_context_menu)

        # Additional columns options
        additional_columns_frame = QFrame()
        additional_columns_layout = QHBoxLayout()
        additional_columns_layout.setContentsMargins(0, 0, 0, 0)
        additional_columns_frame.setLayout(additional_columns_layout)

        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        additional_columns_layout.addItem(spacer)

        for column in self.additional_columns:
            checkbox = QCheckBox(column.title)
            checkbox.stateChanged.connect(self.__update_table)
            self.additional_column_checkboxes[column.title] = checkbox
            additional_columns_layout.addWidget(checkbox)

        tab_layout.addWidget(additional_columns_frame)

        # Filter options
        filter_frame = QFrame()
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_frame.setLayout(filter_layout)

        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        filter_layout.addItem(spacer)

        for filter_option in self.filters:
            checkbox = QCheckBox(filter_option.title)
            checkbox.stateChanged.connect(self.__update_table)
            self.filter_checkboxes[filter_option.title] = checkbox
            filter_layout.addWidget(checkbox)

        tab_layout.addWidget(filter_frame)

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
        selected_corpus_segment_id: CorpusSegmentId = list(target_corpus_data.segments_ids)[index]
        content_metrics = target_corpus_data.content_metrics[selected_corpus_segment_id]

        self.selected_corpus_segment_id = selected_corpus_segment_id
        self.overview_options_available = [option(selected_target, selected_corpus_segment_id, content_metrics) for option in self.overview_options]
        self.__set_selected_overview_option(self.selected_overview_option_index)

    def __set_selected_overview_option(self, index: int) -> None:
        self.selected_overview_option_index = index
        self.__update_table()

    def __handle_key_press(self, e: Optional[QKeyEvent]) -> None:
        if not e:
            return
        # Check for Ctrl+C (Cmd+C on Mac)
        if e.matches(QKeySequence.StandardKey.Copy):
            self.__copy_selection_to_clipboard()
        else:
            # Handle all other key events normally
            QTableWidget.keyPressEvent(self.table, e)

    def __copy_selection_to_clipboard(self) -> None:

        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            return

        clipboard_text = []
        for range_idx in range(len(selected_ranges)):
            selected_range = selected_ranges[range_idx]
            rows = []
            for row in range(selected_range.topRow(), selected_range.bottomRow() + 1):
                columns = []
                for col in range(selected_range.leftColumn(), selected_range.rightColumn() + 1):
                    item = self.table.item(row, col)
                    if item is not None:
                        columns.append(item.text())
                    else:
                        columns.append("")
                rows.append("\t".join(columns))
            clipboard_text.append("\n".join(rows))

        final_text = "\n".join(clipboard_text)

        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(final_text)


    def __set_opacity(self, item: QTableWidgetItem, opacity: float) -> None:
        default_color = self.table.palette().color(self.table.foregroundRole())
        color = QColor(default_color)
        color.setAlpha(int(opacity * 255))
        item.setForeground(color)

    def __set_table_item(self, row_index: int, col_index: int, value: Union[float, int, str]) -> QTableWidgetItem:
        item = NumericTableWidgetItem(value) if isinstance(value, (float, int)) else QTableWidgetItem(str(value))
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsSelectable)
        self.table.setItem(row_index, col_index, item)
        return item

    def __update_table(self) -> None:

        overview_option_selected = self.overview_options_available[self.selected_overview_option_index]

        self.table_label.setText(overview_option_selected.data_description())

        self.table.setDisabled(True)
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)

        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)

        data = overview_option_selected.data()
        labels = overview_option_selected.labels()

        # Apply active filters
        for filter_option in self.filters:
            if filter_option.is_hidden(overview_option_selected):
                self.filter_checkboxes[filter_option.title].hide()
                continue
            self.filter_checkboxes[filter_option.title].show()
            is_enabled = filter_option.is_enabled(data, overview_option_selected.selected_corpus_content_metrics)
            self.filter_checkboxes[filter_option.title].setDisabled(is_enabled == False)

            if is_enabled and self.filter_checkboxes[filter_option.title].isChecked():
                data = filter_option.filter_data(data, overview_option_selected.selected_corpus_content_metrics)

        # Update visibility of checkboxes based on current labels
        for column in self.additional_columns:
            checkbox = self.additional_column_checkboxes[column.title]
            checkbox.setVisible(not column.should_hide(labels))

        # Add additional columns if checked
        additional_labels: list[str] = []
        additional_data: dict[str, list[Union[float, int, str]]] = {}
        words: Optional[list[WordToken]] = None

        for column in self.additional_columns:
            checkbox = self.additional_column_checkboxes[column.title]
            if checkbox.isChecked() and not column.should_hide(labels):
                if words is None:
                    words = [row_data[0] for row_data in data if isinstance(row_data[0], str)]
                additional_column_values = column.get_values(words, overview_option_selected.selected_corpus_content_metrics)

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

        # ignore list
        overview_option_selected.selected_corpus_content_metrics.language_data.load_data({overview_option_selected.selected_corpus_content_metrics.lang_data_id})
        ignore_list = overview_option_selected.selected_corpus_content_metrics.language_data.get_ignore_list(overview_option_selected.selected_corpus_content_metrics.lang_data_id)

        # Populate the table
        for row_index, (row_word, row_data) in enumerate(data):

            # Column for word of row
            first_column_item = self.__set_table_item(row_index, 0, str(row_word))
            if row_word in ignore_list:
                self.__set_opacity(first_column_item, 0.5)

            # Original columns
            for col_index, value in enumerate(row_data, start=1):
                self.__set_table_item(row_index, col_index, value)

            # Additional columns
            for col_index, column_title in enumerate(additional_labels, start=len(row_data)+1):
                value = additional_data[column_title][row_index]
                self.__set_table_item(row_index, col_index, value)

        # Configure table header
        horizontal_header = self.table.horizontalHeader()
        if horizontal_header is not None:
            horizontal_header.setStretchLastSection(True)
            for col_index in range(len(combined_labels)):
                horizontal_header.setSectionResizeMode(col_index, horizontal_header.ResizeMode.Interactive)

            # Set default column widths
            if table_viewport := self.table.viewport():
                table_width = table_viewport.width()
                default_column_width = table_width // len(combined_labels)
                for col_index in range(len(combined_labels)):
                    self.table.setColumnWidth(col_index, default_column_width)

            # Make the last column stretch to fill remaining space
            horizontal_header.setStretchLastSection(True)

        # Allow sorting and updates again
        self.table.setSortingEnabled(True)
        self.table.setUpdatesEnabled(True)
        self.table.setDisabled(False)

    def __show_context_menu(self, position: QPoint) -> None:
        menu = QMenu()

        # Get the row under the cursor
        row = self.table.rowAt(position.y())
        if row < 0:
            return

        word_token_item = self.table.item(row, 0)
        if not word_token_item:
            return

        word_token = WordToken(word_token_item.text())
        target_corpus_data = self.__get_selected_target_corpus_data()
        content_metrics = target_corpus_data.content_metrics[self.selected_corpus_segment_id]

        # Add menu items
        show_cards_action = None
        if word_token in content_metrics.cards_per_word:
            show_cards_action = menu.addAction("Show cards")
            menu.addSeparator()
        copy_word_action = menu.addAction("Copy word")

        # Show the menu at cursor position
        action = menu.exec(QCursor.pos())
        if action is None:
            return

        # Handle menu actions
        if action == show_cards_action:
            self.__on_menu_word_show_cards(word_token, content_metrics)
        elif action == copy_word_action:
            self.__on_menu_word_copy(word_token)

    def __on_menu_word_show_cards(self, word: WordToken, content_metrics: SegmentContentMetrics) -> None:

        note_ids = set(card.nid for card in content_metrics.cards_per_word[word])
        batched_note_ids = batched(note_ids, 300)  # prevent "Expression tree is too large" error
        queries = []
        for note_ids in batched_note_ids:
            search_query = " OR ".join("nid:{}".format(note_id) for note_id in note_ids)
            search_query = "({})".format(search_query)
            queries.append(search_query)
        search_query = " OR ".join(queries)

        browser: Browser = dialogs.open('Browser', self.fm_window.mw)
        browser.search_for(self.col.build_search_string(search_query))

    def __on_menu_word_copy(self, word: str) -> None:

        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(word)
