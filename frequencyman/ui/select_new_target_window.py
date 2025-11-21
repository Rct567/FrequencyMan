"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from collections import defaultdict
import random
import re
from collections.abc import Sequence

from anki.collection import Collection
from anki.decks import DeckNameId
from anki.models import NotetypeNameIdUseCount
from aqt.utils import askUser, showWarning, showInfo, getOnlyText as getOnlyTextDialog
from aqt.qt import (
    QDialog, QLabel, QSpacerItem, QSizePolicy, QPushButton, QVBoxLayout,
    QLineEdit, QStringListModel, QListView, QAbstractItemView
)

from ..static_lang_data import NAMES_FOR_THE_ENGLISH_LANGUAGE, LANGUAGE_NAMES_ENG_AND_NATIVE
from ..target import ConfiguredTargetNote, ValidConfiguredTarget

from .main_window import FrequencyManMainWindow


class ItemsList:

    view: QListView
    model: QStringListModel

    def __init__(self, items: list[str], multi_select: bool = False):

        self.view = QListView()
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.model = QStringListModel(items)
        self.view.setModel(self.model)

        if multi_select:
            self.view.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)


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
        deck_names = [deck.name for deck in self.__get_sorted_decks()]
        self.deck_list = ItemsList(deck_names)
        if len(deck_names) > 10:
            self.deck_list.view.setMinimumHeight(185)
        if (selection_model := self.deck_list.view.selectionModel()) is not None:
            selection_model.selectionChanged.connect(self.__on_deck_selection_change)
        self.deck_filter.textChanged.connect(self.__filter_decks)

        layout.addWidget(self.deck_label)
        layout.addWidget(self.deck_filter)
        layout.addWidget(self.deck_list.view)

        # Note type selection
        self.note_label = QLabel("Note type:")
        self.note_label.setContentsMargins(0, 10, 0, 0)
        self.note_filter = QLineEdit()
        self.note_filter.setPlaceholderText("Filter note types...")
        self.note_list = ItemsList([model.name for model in self.__get_sorted_note_types()])
        if (selection_model := self.note_list.view.selectionModel()) is not None:
            selection_model.selectionChanged.connect(self.__on_note_selection_change)
        self.note_filter.textChanged.connect(self.__filter_notes)

        layout.addWidget(self.note_label)
        layout.addWidget(self.note_filter)
        layout.addWidget(self.note_list.view)

        # Field selection
        self.fields_label = QLabel("Fields:")
        self.fields_label.setContentsMargins(0, 10, 0, 0)
        self.fields_label.setMargin(0)
        self.fields_label.setVisible(False)
        self.fields_list = ItemsList([], multi_select=True)
        self.fields_list.view.setVisible(False)
        layout.addWidget(self.fields_label)
        layout.addWidget(self.fields_list.view)

        layout.addItem(QSpacerItem(100, 25, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        layout.addItem(QSpacerItem(100, 10, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed))

        self.pre_submit_info_label = QLabel("")
        self.pre_submit_info_label.setVisible(False)
        layout.addWidget(self.pre_submit_info_label)

        # Add target button
        self.submit_button = QPushButton("Add Target")
        self.submit_button.setEnabled(False)
        self.submit_button.clicked.connect(self.__submit_button_clicked)
        layout.addWidget(self.submit_button)

    def __get_sorted_decks(self) -> Sequence[DeckNameId]:
        return [deck for deck in self.col.decks.all_names_and_ids(include_filtered=False)]

    def __get_sorted_note_types(self) -> Sequence[NotetypeNameIdUseCount]:
        return [model for model in sorted(self.col.models.all_use_counts(), key=lambda x: x.use_count, reverse=True)]

    def __get_note_types_counts_by_deck(self, deck_name: str) -> dict[str, int]:

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

    def __set_decks_list(self, strings: Sequence[str]) -> None:
        self.deck_list.model.setStringList(strings)
        self.__on_deck_selection_change()  # deselected

    def __set_note_types_list(self, strings: Sequence[str]) -> None:
        self.note_list.model.setStringList(strings)
        self.__on_note_selection_change()  # deselected

    def __filter_decks(self, needle: str) -> None:
        filtered_decks = [deck.name for deck in self.__get_sorted_decks() if needle.lower() in deck.name.lower()]
        self.__set_decks_list(filtered_decks)

    def __filter_notes(self, needle: str) -> None:
        filtered_notes = [model.name for model in self.__get_sorted_note_types() if needle.lower() in model.name.lower()]
        self.__set_note_types_list(filtered_notes)

    def __on_deck_selection_change(self) -> None:
        if (selection_model := self.deck_list.view.selectionModel()) is None:
            return
        selected_indexes = selection_model.selectedIndexes()
        if selected_indexes:
            self.selected_deck = selected_indexes[0].data()
        else:
            self.selected_deck = ""

        # update note types list based on selected deck
        if self.selected_deck:
            note_typed_counted_by_deck = list(self.__get_note_types_counts_by_deck(self.selected_deck).keys())
            if note_typed_counted_by_deck:
                self.__set_note_types_list(note_typed_counted_by_deck)

        self.__on_selection_change()

    def __on_note_selection_change(self) -> None:
        if (selection_model := self.note_list.view.selectionModel()) is None:
            return
        selected_indexes = selection_model.selectedIndexes()
        if selected_indexes:
            self.selected_note_type = selected_indexes[0].data()
            self.__update_fields_list()
        else:
            self.selected_note_type = ""
        self.__on_selection_change()

    def __on_selection_change(self) -> None:
        self.fields_label.setVisible(self.selected_note_type != "")
        self.fields_list.view.setVisible(self.selected_note_type != "")
        self.submit_button.setEnabled(self.selected_deck != "" and self.selected_note_type != "")

        if self.selected_deck != "" and self.selected_note_type != "":
            target_result = self.col.find_cards("\"deck:{}\" AND note:\"{}\"".format(self.selected_deck, self.selected_note_type))
            num_cards_text = ("{} card" if len(target_result) == 1 else "{:n} cards").format(len(target_result))
            self.pre_submit_info_label.setText("Found {} for selected deck and note type.".format(num_cards_text))
            self.pre_submit_info_label.setVisible(True)
        else:
            self.pre_submit_info_label.setVisible(False)

    def __update_fields_list(self) -> None:
        selected_note_type_name = self.selected_note_type
        if not selected_note_type_name:
            return

        note_model = self.col.models.by_name(selected_note_type_name)
        if note_model is None:
            return

        note_field_names = [str(field['name']) for field in note_model['flds']]
        self.fields_list.model.setStringList(note_field_names)

    @staticmethod
    def get_lang_data_id_suggestion(field_name: str, note_type_name: str, deck_name: str) -> str:
        field_name_lower = field_name.lower()
        note_type_name_lower = note_type_name.lower()
        deck_name_lower = deck_name.lower()

        if '_' in field_name or len(field_name) == 2:
            for lang_data_id in LANGUAGE_NAMES_ENG_AND_NATIVE.keys():
                if field_name.startswith(lang_data_id+'_') or field_name_lower == lang_data_id.lower():
                    return lang_data_id

        if field_name_lower in {'translation', 'meaning', 'definition'}:
            return 'en'

        lang_names: dict[str, list[str]] = {}

        for lang_id, lang_name_data in LANGUAGE_NAMES_ENG_AND_NATIVE.items():
            names = re.split(r'[;,.()\s]', (lang_name_data['name']+";"+lang_name_data['nativeName']))
            lang_names[lang_id] = [name.strip().lower() for name in names if isinstance(name, str) and len(name.encode('utf-8')) > 2]
            if lang_id == 'en':
                lang_names[lang_id] += NAMES_FOR_THE_ENGLISH_LANGUAGE

        # check by deck name
        if field_name_lower in {'sentence', 'word'}:
            for lang_id, names in lang_names.items():
                for name in names:
                    if name in deck_name_lower:
                        return lang_id

        # check by field name
        for lang_id, names in lang_names.items():
            for name in names:
                if name in field_name_lower:
                    return lang_id

        # check by note type name
        for lang_id, names in lang_names.items():
            for name in names:
                if name in note_type_name_lower:
                    return lang_id

        return ""

    def __submit_button_clicked(self) -> None:
        selected_indexes = self.fields_list.view.selectedIndexes()
        selected_fields = [self.fields_list.model.data(index) for index in selected_indexes]
        self.selected_fields = {field_name: '' for field_name in selected_fields}
        for field_name in self.selected_fields.keys():
            default_lang_data_id = self.get_lang_data_id_suggestion(field_name, self.selected_note_type, self.selected_deck)
            field_lang_data_id = getOnlyTextDialog("Language id for field '{}' of note type '{}'?".format(field_name, self.selected_note_type), default=default_lang_data_id, parent=self)
            self.selected_fields[field_name] = field_lang_data_id
        self.accept()

    def get_selected_target(self) -> ValidConfiguredTarget:
        new_target_note: ConfiguredTargetNote = {'name': self.selected_note_type, 'fields': self.selected_fields}
        return ValidConfiguredTarget({
            'deck': self.selected_deck,
            'notes': [new_target_note],
        })