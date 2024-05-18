"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from typing import Optional

from anki.collection import Collection
from aqt.utils import askUser, showWarning, showInfo, getOnlyText
from aqt import QAction, QSpacerItem, QSizePolicy, QApplication
from aqt.qt import *

from .main_window import FrequencyManMainWindow


from ..target_list import ConfiguredTarget, ConfiguredTargetNote


class SelectNewTargetWindow(QDialog):

    selected_deck: str
    selected_note_type: str
    selected_fields: dict[str, str]


    def __init__(self, fm_window: FrequencyManMainWindow, col: Collection):

        super().__init__(fm_window)
        self.col = col
        self.setWindowTitle("Select new target")
        self.setLayout(QVBoxLayout())

        layout = self.layout()

        if layout is None:
            return

        self.selected_deck = ""
        self.selected_note_type = ""

        # Deck selection
        self.deck_label = QLabel("Deck:")
        self.deck_combo = QComboBox()
        self.deck_combo.addItem("")  # Empty default
        self.deck_combo.addItems([str(deck.name) for deck in col.decks.all_names_and_ids(include_filtered=False)])
        self.deck_combo.currentIndexChanged.connect(self.on_selection_change)
        layout.addWidget(self.deck_label)
        layout.addWidget(self.deck_combo)

        # Note type selection
        self.note_label = QLabel("Note type:")
        self.note_label.setContentsMargins(0, 10, 0, 0)
        self.note_combo = QComboBox()
        self.note_combo.addItem("")  # Empty default
        self.note_combo.addItems([str(model.name) for model in col.models.all_names_and_ids()])
        self.note_combo.currentIndexChanged.connect(self.update_fields_list)
        self.note_combo.currentIndexChanged.connect(self.on_selection_change)
        layout.addWidget(self.note_label)
        layout.addWidget(self.note_combo)

        # Field selection
        self.fields_label = QLabel("Fields:")
        self.fields_label.setContentsMargins(0, 10, 0, 0)
        self.fields_label.setMargin(0)
        self.fields_label.setVisible(False)
        self.fields_list = QWidget()
        self.fields_list.setVisible(False)
        self.fields_list_layout = QVBoxLayout()
        self.fields_list.setLayout(self.fields_list_layout)
        layout.addWidget(self.fields_label)
        layout.addWidget(self.fields_list)

        #
        layout.addItem(QSpacerItem(100, 25, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        layout.addItem(QSpacerItem(100, 10, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed))

        #
        self.pre_submit_info_label = QLabel("")
        self.pre_submit_info_label.setVisible(False)
        layout.addWidget(self.pre_submit_info_label)

        # Add target button

        self.submit_button = QPushButton("Add Target")
        self.submit_button.setEnabled(False)  # Initially disabled
        self.submit_button.clicked.connect(self.submit_button_clicked)

        layout.addWidget(self.submit_button)


    def on_selection_change(self):

        self.selected_deck = self.deck_combo.currentText()
        self.selected_note_type = self.note_combo.currentText()

        # Make fields list visible if note type is selected
        self.fields_label.setVisible(self.selected_note_type != "")
        self.fields_list.setVisible(self.selected_note_type != "")

        # Enable the 'add target' button only if both are selected
        self.submit_button.setEnabled(self.selected_deck != "" and self.selected_note_type != "")

        # Info about the selected target
        if self.selected_deck != "" and self.selected_note_type != "":
            target_result = self.col.find_cards("\"deck:{}\" AND note:\"{}\"".format(self.selected_deck, self.selected_note_type))
            self.pre_submit_info_label.setText("Found {:n} cards for selected deck and note type.".format(len(target_result)))
            self.pre_submit_info_label.setVisible(True)
        else:
            self.pre_submit_info_label.setVisible(False)

    def update_fields_list(self):

        # Clear existing checkboxes
        for i in reversed(range(self.fields_list_layout.count())):
            item = self.fields_list_layout.itemAt(i)
            if item is None:
                continue
            widget_to_remove = item.widget()
            if widget_to_remove is None:
                continue
            self.fields_list_layout.removeWidget(widget_to_remove)
            widget_to_remove.setParent(None)

        # Get selected note type
        selected_note_type_name = self.note_combo.currentText()
        if not selected_note_type_name:
            return

        # Find model by name
        note_model = self.col.models.by_name(selected_note_type_name)

        if note_model is None:
            return

        note_field_names = [str(field['name']) for field in note_model['flds']]

        # Add checkboxes for each field
        for field_name in note_field_names:
            checkbox = QCheckBox(field_name)
            self.fields_list_layout.addWidget(checkbox)

    def submit_button_clicked(self):

        selected_fields = [checkbox.text() for checkbox in self.fields_list.findChildren(QCheckBox) if checkbox.isChecked()]

        self.selected_fields = {field_name: '' for field_name in selected_fields}
        for field_name in self.selected_fields.keys():
            default_lang_data_id = "en" if field_name == "Front" else ""
            field_lang_data_id = getOnlyText("Language id for field '{}' of note type '{}'?".format(field_name, self.selected_note_type), default=default_lang_data_id)
            self.selected_fields[field_name] = field_lang_data_id

        self.accept()

    def get_selected_target(self) -> ConfiguredTarget:

        new_target_note: ConfiguredTargetNote = {'name': self.selected_note_type, 'fields': self.selected_fields}
        new_target: ConfiguredTarget = {'deck': self.selected_deck, 'notes': [new_target_note]}
        return new_target