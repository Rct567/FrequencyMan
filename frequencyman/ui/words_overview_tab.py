"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, ClassVar, Optional, Union

from aqt.qt import (
    QLabel, QSpacerItem, QSizePolicy, QLayout, QTimer, QHBoxLayout, QFrame, Qt, QApplication,
    QColor, QComboBox, QCursor, QKeyEvent, QKeySequence, QMenu, QPoint, QTableWidget, QTableWidgetItem, QCheckBox,
    QStandardItemModel, QStandardItem
)
from aqt import dialogs
from aqt.utils import showWarning

if TYPE_CHECKING:
    from anki.collection import Collection
    from ..lib.addon_config import AddonConfig
    from ..target_list import TargetList
    from ..target import Target
    from ..target_corpus_data import SegmentContentMetrics, TargetCorpusData, CorpusSegmentId
    from collections.abc import Sequence
    from aqt.browser.browser import Browser


from .words_overview_tab_additional_columns import (
    AdditionalColumn, WordFrequencyColumn, WordFamiliarityColumn, NumberOfCardsColumn, NumberOfNotesColumn, WordPresenceColumn)
from .words_overview_tab_overview_options import (
    AllWordsOverview, LearningWordsOverview, MatureWordsOverview, WordsOverviewOption, WordFamiliarityOverview, WordFrequencyOverview, InternalWordFrequencyOverview, WordUnderexposureOverview,
    WordFamiliaritySweetspotOverview, NotInWordFrequencyListsOverview,
    NotInTargetCardsOverview, LonelyWordsOverview, NewWordsOverview, FocusWordsOverview)
from .words_overview_filters import FilterOption, IgnoredWordsFilter, LearningWordsFilter, MatureWordsFilter

from .main_window import FrequencyManMainWindow, FrequencyManTab

from ..lib.utilities import batched, override
from ..text_processing import WordToken


class KeyedTable(QTableWidget):
    def __init__(self, key_press_callback: Optional[Callable[[QKeyEvent], None]] = None, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._key_press_callback = key_press_callback

    @override
    def keyPressEvent(self, e: Optional[QKeyEvent]) -> None:
        if e is not None:
            if self._key_press_callback:
                self._key_press_callback(e)
                return
        super().keyPressEvent(e)


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

    id = 'words_overview'
    name = 'Words overview'

    fm_config: AddonConfig

    target_list: TargetList
    selected_target_index: int
    selected_overview_option_index: int
    selected_overview_option: Optional[type[WordsOverviewOption]]
    selected_target_by_id_str: Optional[str]
    selected_lang_id: Optional[str]
    selected_corpus_segment_id: Optional[CorpusSegmentId]
    targets_dropdown: QComboBox
    target_corpus_segment_dropdown: QComboBox
    OVERVIEW_OPTIONS: ClassVar[dict[str, Sequence[type[WordsOverviewOption]]]] = {
        "Factors": (
            WordFamiliarityOverview,
            WordFrequencyOverview,
            InternalWordFrequencyOverview,
            WordUnderexposureOverview,
            WordFamiliaritySweetspotOverview,
        ),
        "Content": (
            NewWordsOverview,
            AllWordsOverview,
            FocusWordsOverview,
            LearningWordsOverview,
            MatureWordsOverview,
            LonelyWordsOverview,
        ),
        "Word frequency lists": (
            NotInWordFrequencyListsOverview,
            NotInTargetCardsOverview,
        ),
    }
    overview_options_available: list[Optional[WordsOverviewOption]]
    table_label: QLabel
    table: KeyedTable

    additional_columns: list[AdditionalColumn]
    additional_column_checkboxes: dict[str, QCheckBox]

    filters: list[FilterOption]
    filter_checkboxes: dict[str, QCheckBox]


    def reset_selections(self) -> None:
        self.selected_target_index = 0
        self.selected_corpus_segment_id = None
        self.selected_overview_option_index = 1 # 0 is header

    def __init__(self, fm_config: AddonConfig, fm_window: FrequencyManMainWindow, col: Collection) -> None:

        super().__init__(fm_window, fm_config, col)

        self.fm_config = fm_config

        self.reset_selections()

        self.additional_columns = [
            WordFrequencyColumn(),
            WordFamiliarityColumn(),
            WordPresenceColumn(),
            NumberOfCardsColumn(),
            NumberOfNotesColumn()
        ]
        self.additional_column_checkboxes = {}
        self.filters = [
            IgnoredWordsFilter(),
            LearningWordsFilter(),
            MatureWordsFilter()
        ]
        self.filter_checkboxes = {}

    def __load_target_list(self) -> None:

        self.target_list = self.init_new_target_list()

        if 'reorder_target_list' not in self.fm_config:
            raise Exception("'reorder_target_list' is not defined.")

        defined_target_list = self.fm_config['reorder_target_list']
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

        # reset selections
        self.reset_selections()

        # Target selection
        label = QLabel("Target:")
        tab_layout.addWidget(label)

        self.targets_dropdown = QComboBox()
        self.targets_dropdown.addItems([target.name for target in self.target_list])
        if hasattr(self, 'selected_target_by_id_str') and isinstance(self.selected_target_by_id_str, str):
            if (selected_target_index := self.get_target_index_by_id(self.selected_target_by_id_str)) is not None:
                self.selected_target_index = selected_target_index
                self.targets_dropdown.setCurrentIndex(selected_target_index)
            self.selected_target_by_id_str = None

        self.targets_dropdown.currentIndexChanged.connect(self.__set_selected_target)
        tab_layout.addWidget(self.targets_dropdown)

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
        model = QStandardItemModel()
        self.overview_options_dropdown.setModel(model)
        for category, options in self.OVERVIEW_OPTIONS.items():
            # Add category header with visual prefix
            header_item = QStandardItem(category)
            header_item.setEnabled(False)
            header_item.setSelectable(False)
            # Set font to italic to distinguish headers
            font = header_item.font()
            font.setItalic(True)
            header_item.setFont(font)
            model.appendRow(header_item)
            # Add options with indentation
            for option in options:
                item = QStandardItem("  " + option.title)
                model.appendRow(item)
        self.overview_options_dropdown.currentIndexChanged.connect(self.__set_selected_overview_option)
        tab_layout.addWidget(self.overview_options_dropdown)

        # Table
        self.table_label = QLabel("")
        self.table_label.setStyleSheet("margin-top:8px;")
        tab_layout.addWidget(self.table_label)
        self.table = KeyedTable(key_press_callback=self.__handle_table_key_press)
        tab_layout.addWidget(self.table)

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
        QTimer.singleShot(1, lambda: self.__set_selected_target(self.selected_target_index))

    def get_target_index_by_id(self, target_id: str) -> Optional[int]:
        for target_index, target in enumerate(self.target_list):
            if target.id_str == target_id:
                return target_index

    def __get_selected_target(self) -> Target:
        return self.target_list[self.selected_target_index]

    def __get_selected_target_corpus_data(self) -> TargetCorpusData:
        selected_target = self.__get_selected_target()
        return selected_target.get_corpus_data(selected_target.get_cards())

    def __set_selected_target(self, index: int) -> None:

        self.selected_target_index = index
        selected_target_corpus_data = self.__get_selected_target_corpus_data()

        self.target_corpus_segment_dropdown.blockSignals(True)
        self.target_corpus_segment_dropdown.clear()
        self.target_corpus_segment_dropdown.addItems([segment_id for segment_id in selected_target_corpus_data.segments_ids])
        self.target_corpus_segment_dropdown.blockSignals(False)

        if hasattr(self, 'selected_lang_id') and isinstance(self.selected_lang_id, str):
            lang_id_matched = False
            for segment_index, segment_id in enumerate(selected_target_corpus_data.segments_ids):
                if self.selected_lang_id.lower() == segment_id.lower():
                    lang_id_matched = True
                    self.__set_selected_target_corpus_segment(segment_index)
                    break
            if not lang_id_matched:
                showWarning("Language id '{}' not found as segment in corpus data of target #{}.".format(self.selected_lang_id, self.selected_target_index))
                self.__set_selected_target_corpus_segment(0)
            self.selected_lang_id = None
        else:
            self.__set_selected_target_corpus_segment(0)


    def __selected_target_has_content(self) -> bool:

        if not len(self.__get_selected_target().get_cards()) > 0:
            return False

        if not self.__get_selected_target_corpus_data().content_metrics:
            return False

        return True


    def __set_selected_target_corpus_segment(self, index: int) -> None:

        if self.target_corpus_segment_dropdown.currentIndex() != index:
            self.target_corpus_segment_dropdown.setCurrentIndex(index)
            return

        selected_target = self.__get_selected_target()
        target_corpus_data = self.__get_selected_target_corpus_data()
        selected_corpus_segment_id: CorpusSegmentId = list(target_corpus_data.segments_ids)[index]

        if self.__selected_target_has_content():
            content_metrics = target_corpus_data.content_metrics[selected_corpus_segment_id]
            self.selected_corpus_segment_id = selected_corpus_segment_id
            self.overview_options_available = []
            for options in self.OVERVIEW_OPTIONS.values():
                self.overview_options_available.append(None)  # Header
                for option in options:
                    self.overview_options_available.append(option(selected_target, selected_corpus_segment_id, content_metrics))
        else:
            self.overview_options_available = []

        if hasattr(self, 'selected_overview_option') and self.selected_overview_option is not None and issubclass(self.selected_overview_option, WordsOverviewOption):
            current_idx = 0
            found = False
            for options in self.OVERVIEW_OPTIONS.values():
                current_idx += 1  # Header
                for option in options:
                    if option == self.selected_overview_option:
                        self.selected_overview_option_index = current_idx
                        found = True
                        break
                    current_idx += 1
                if found:
                    break
            self.selected_overview_option = None

        self.__set_selected_overview_option(self.selected_overview_option_index)


    def __set_selected_overview_option(self, index: int) -> None:
        """Set the selected overview option by index."""
        if self.overview_options_dropdown.currentIndex() != index:
            self.overview_options_dropdown.setCurrentIndex(index)
            return

        # If it's a header (None in available options), don't select it
        if index < len(self.overview_options_available) and self.overview_options_available[index] is None:
            return

        self.selected_overview_option_index = index
        self.__update_table()

    def __handle_table_key_press(self, e: QKeyEvent) -> None:

        # Check for Ctrl+C (Cmd+C on Mac)
        if e.matches(QKeySequence.StandardKey.Copy):
            self.__copy_selection_to_clipboard()

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

        if not self.__selected_target_has_content():
            self.table.setDisabled(True)
            self.table.clearContents()
            self.table.setRowCount(0)
            return

        overview_option_selected = self.overview_options_available[self.selected_overview_option_index]

        if overview_option_selected is None:
            return

        self.table_label.setText(overview_option_selected.data_description())

        self.table.setDisabled(True)
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)

        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)

        data = overview_option_selected.data()
        labels = overview_option_selected.labels()

        # Apply active filters
        for filter_option in self.filters:
            if filter_option.is_hidden(overview_option_selected, overview_option_selected.selected_corpus_content_metrics):
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
        ignored_words = overview_option_selected.selected_corpus_content_metrics.ignored_words

        # Populate the table
        for row_index, (row_word, row_data) in enumerate(data):

            # Column for word of row
            first_column_item = self.__set_table_item(row_index, 0, str(row_word))
            if row_word in ignored_words:
                self.__set_opacity(first_column_item, 0.5)

            # Original columns
            for col_index, value_numeric in enumerate(row_data, start=1):
                self.__set_table_item(row_index, col_index, value_numeric)

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

        if not self.selected_corpus_segment_id:
            return

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
        for note_ids_batch in batched_note_ids:
            search_query = " OR ".join("nid:{}".format(note_id) for note_id in note_ids_batch)
            search_query = "({})".format(search_query)
            queries.append(search_query)
        search_query = " OR ".join(queries)

        browser: Browser = dialogs.open('Browser', self.fm_window.mw)
        browser.search_for(self.col.build_search_string(search_query))

    def __on_menu_word_copy(self, word: str) -> None:

        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(word)
