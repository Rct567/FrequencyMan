"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from collections import defaultdict
import random
from typing import Iterable, Sequence

from anki.collection import Collection
from anki.decks import DeckNameId
from anki.models import NotetypeNameIdUseCount
from aqt.utils import askUser, showWarning, showInfo, getOnlyText
from aqt import QAction, QSpacerItem, QSizePolicy, QApplication
from aqt.qt import *

from ..lib.utilities import var_dump, var_dump_log

from .main_window import FrequencyManMainWindow

from ..target_list import ConfiguredTarget, ConfiguredTargetDataNote


class SelectNewTargetWindow(QDialog):

    selected_deck: str
    selected_note_type: str
    selected_fields: dict[str, str]


    def __init__(self, fm_window: FrequencyManMainWindow, col: Collection):

        super().__init__(fm_window)
        self.col = col
        self.setWindowTitle("Select new target")
        self.setMinimumWidth(500)
        self.setLayout(QVBoxLayout())

        layout = self.layout()
        if layout is None:
            return

        self.selected_deck = ""
        self.selected_note_type = ""

        # Deck selection
        self.deck_label = QLabel("Deck:")
        self.deck_filter = QLineEdit()
        self.deck_filter.setPlaceholderText("Filter decks...")
        self.deck_list_view = QListView()
        deck_names = [deck.name for deck in self.get_sorted_decks()]
        self.deck_list_model = QStringListModel(deck_names)
        if len(deck_names) > 10:
            self.deck_list_view.setMinimumHeight(185)
        self.deck_list_view.setModel(self.deck_list_model)
        if (selection_model := self.deck_list_view.selectionModel()) is not None:
            selection_model.selectionChanged.connect(self.on_deck_selection_change)
        self.deck_filter.textChanged.connect(self.filter_decks)

        layout.addWidget(self.deck_label)
        layout.addWidget(self.deck_filter)
        layout.addWidget(self.deck_list_view)

        # Note type selection
        self.note_label = QLabel("Note type:")
        self.note_label.setContentsMargins(0, 10, 0, 0)
        self.note_filter = QLineEdit()
        self.note_filter.setPlaceholderText("Filter note types...")
        self.note_list_view = QListView()
        #self.note_list_view.setMinimumHeight(200)
        self.note_list_model = QStringListModel([model.name for model in self.get_sorted_note_types()])

        self.note_list_view.setModel(self.note_list_model)
        if (selection_model := self.note_list_view.selectionModel()) is not None:
            selection_model.selectionChanged.connect(self.on_note_selection_change)
        self.note_filter.textChanged.connect(self.filter_notes)

        layout.addWidget(self.note_label)
        layout.addWidget(self.note_filter)
        layout.addWidget(self.note_list_view)

        # Field selection
        self.fields_label = QLabel("Fields:")
        self.fields_label.setContentsMargins(0, 10, 0, 0)
        self.fields_label.setMargin(0)
        self.fields_label.setVisible(False)
        self.fields_list_view = QListView()
        self.fields_list_view.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.fields_list_view.setVisible(False)
        self.fields_list_model = QStringListModel()
        self.fields_list_view.setModel(self.fields_list_model)
        layout.addWidget(self.fields_label)
        layout.addWidget(self.fields_list_view)

        layout.addItem(QSpacerItem(100, 25, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        layout.addItem(QSpacerItem(100, 10, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed))

        self.pre_submit_info_label = QLabel("")
        self.pre_submit_info_label.setVisible(False)
        layout.addWidget(self.pre_submit_info_label)

        # Add target button
        self.submit_button = QPushButton("Add Target")
        self.submit_button.setEnabled(False)  # Initially disabled
        self.submit_button.clicked.connect(self.submit_button_clicked)
        layout.addWidget(self.submit_button)

    def get_sorted_decks(self) -> list[DeckNameId]:
        return [deck for deck in self.col.decks.all_names_and_ids(include_filtered=False)]

    def get_sorted_note_types(self) -> list[NotetypeNameIdUseCount]:
        return [model for model in sorted(self.col.models.all_use_counts(), key=lambda x: x.use_count, reverse=True)]


    def get_note_types_counts_by_deck(self, deck_name: str) -> dict[str, int]:

        card_ids = list(self.col.find_cards("deck:\"{}\"".format(deck_name)))
        if len(card_ids) == 0:
            return {}

        # Get random subset of cards in the deck

        random.shuffle(card_ids)
        card_ids = card_ids[:2000]

        # Count note types per card

        note_type_counts: dict[str, int] = defaultdict(int)

        for card_id in card_ids:
            card = self.col.get_card(card_id)
            note = self.col.get_note(card.nid)
            note_type = self.col.models.get(note.mid)
            if note_type:
                note_type_counts[note_type['name']] += 1

        sorted_note_type_counts = dict(sorted(note_type_counts.items(), key=lambda x: x[1], reverse=True))

        return sorted_note_type_counts

    def set_decks_list(self, strings: Sequence[str]):
        self.deck_list_model.setStringList(strings)
        self.on_deck_selection_change() # deselected

    def set_note_types_list(self, strings: Sequence[str]):
        self.note_list_model.setStringList(strings)
        self.on_note_selection_change() # deselected

    def filter_decks(self, text: str):
        filtered_decks = [deck.name for deck in self.get_sorted_decks() if text.lower() in deck.name.lower()]
        self.set_decks_list(filtered_decks)

    def filter_notes(self, text: str):
        filtered_notes = [model.name for model in self.get_sorted_note_types() if text.lower() in model.name.lower()]
        self.set_note_types_list(filtered_notes)

    def on_deck_selection_change(self):
        if (selection_model := self.deck_list_view.selectionModel()) is None:
            return
        selected_indexes = selection_model.selectedIndexes()
        if selected_indexes:
            self.selected_deck = selected_indexes[0].data()
        else:
            self.selected_deck = ""

        # update note types list based on selected deck
        if self.selected_deck:
            note_typed_counted_by_deck = list(self.get_note_types_counts_by_deck(self.selected_deck).keys())
            if note_typed_counted_by_deck:
                self.set_note_types_list(note_typed_counted_by_deck)

        self.on_selection_change()

    def on_note_selection_change(self):
        if (selection_model := self.note_list_view.selectionModel()) is None:
            return
        selected_indexes = selection_model.selectedIndexes()
        if selected_indexes:
            self.selected_note_type = selected_indexes[0].data()
            self.update_fields_list()
        else:
            self.selected_note_type = ""
        self.on_selection_change()

    def on_selection_change(self):
        self.fields_label.setVisible(self.selected_note_type != "")
        self.fields_list_view.setVisible(self.selected_note_type != "")
        self.submit_button.setEnabled(self.selected_deck != "" and self.selected_note_type != "")

        if self.selected_deck != "" and self.selected_note_type != "":
            target_result = self.col.find_cards("\"deck:{}\" AND note:\"{}\"".format(self.selected_deck, self.selected_note_type))
            self.pre_submit_info_label.setText("Found {:n} cards for selected deck and note type.".format(len(target_result)))
            self.pre_submit_info_label.setVisible(True)
        else:
            self.pre_submit_info_label.setVisible(False)

    def update_fields_list(self):
        selected_note_type_name = self.selected_note_type
        if not selected_note_type_name:
            return

        note_model = self.col.models.by_name(selected_note_type_name)
        if note_model is None:
            return

        note_field_names = [str(field['name']) for field in note_model['flds']]
        self.fields_list_model.setStringList(note_field_names)

    def submit_button_clicked(self):
        selected_indexes = self.fields_list_view.selectedIndexes()
        selected_fields = [self.fields_list_model.data(index) for index in selected_indexes]
        self.selected_fields = {field_name: '' for field_name in selected_fields}
        for field_name in self.selected_fields.keys():
            default_lang_data_id = "en" if field_name == "Front" else ""
            field_lang_data_id = getOnlyText("Language id for field '{}' of note type '{}'?".format(field_name, self.selected_note_type), default=default_lang_data_id)
            self.selected_fields[field_name] = field_lang_data_id
        self.accept()

    def get_selected_target(self) -> ConfiguredTarget:
        new_target_note: ConfiguredTargetDataNote = {'name': self.selected_note_type, 'fields': self.selected_fields}
        return ConfiguredTarget({'deck': self.selected_deck, 'notes': [new_target_note]})
