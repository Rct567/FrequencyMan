from functools import partial
import json
from typing import Tuple
from xmlrpc.client import Boolean

from anki.collection import Collection

from aqt.utils import askUser, showWarning, showInfo
from aqt import QAction
from aqt.qt import *
from aqt.main import AnkiQt

from .main_window import FrequencyManMainWindow

from ..lib.event_logger import EventLogger
from ..lib.utilities import var_dump_log

from ..target import ConfigTargetDataNotes
from ..word_frequency_list import WordFrequencyLists
from ..target_list import ConfigTargetData, TargetList


class ReorderCardsTab:

    fm_window: FrequencyManMainWindow
    col: Collection
    target_list: TargetList

    targets_input_textarea: QTextEdit
    targets_input_options_line: QWidget
    targets_input_validation_info_txt_line: QLabel
    targets_input_reset_button: QPushButton
    targets_input_save_button: QPushButton

    def __init__(self, fm_window: FrequencyManMainWindow, col: Collection) -> None:

        self.fm_window = fm_window
        self.col = col

        # word frequency lists can be used for all targets
        frequency_lists_dir = os.path.join(self.fm_window.root_dir, 'user_files', 'frequency_lists')
        word_frequency_lists = WordFrequencyLists(frequency_lists_dir)

        # target data
        self.target_list = TargetList(word_frequency_lists)
        if self.fm_window.addon_config and "fm_reorder_target_list" in self.fm_window.addon_config:
            self.target_list.set_targets(self.fm_window.addon_config.get("fm_reorder_target_list", []))

        self.targets_input_textarea = QTextEdit()
        self.targets_input_textarea.setMinimumHeight(300)
        self.targets_input_textarea.setAcceptRichText(False)
        self.targets_input_textarea.setStyleSheet("font-weight: bolder; font-size: 14px; line-height: 1.2;")

        self.__create_targets_input_options_row_widget()

    def create_new_tab(self):

        # Create a new tab and its layout
        (tab_layout, tab) = self.fm_window.create_new_tab('sort_cards', "Sort cards")

        # Textarea widget
        if (self.target_list.has_targets()):
            self.targets_input_textarea.setText(self.target_list.dump_json())
        else:  # when does this even happen?
            example_data_notes_item: ConfigTargetDataNotes = {'name': '** name of notes type **', 'fields': {"Front": "JP", "Back": "EN"}}
            example_target: ConfigTargetData = {'deck': '** name of main deck **', 'notes': [example_data_notes_item]}
            example_target_list = [example_target]
            self.targets_input_textarea.setText(json.dumps(example_target_list, indent=4))

        # User clicked reorder... ask to save to config if new targets have been defined

        def ask_to_save_new_targets_to_config(targets_defined: list[ConfigTargetData]):
            if self.fm_window.addon_config is None or "fm_reorder_target_list" not in self.fm_window.addon_config:
                return
            if self.fm_window.addon_config['fm_reorder_target_list'] == targets_defined:
                return
            if askUser("Defined targets have changed. Save them to config?"):
                self.fm_window.addon_config['fm_reorder_target_list'] = targets_defined
                self.fm_window.addon_config_write(self.fm_window.addon_config)

        # Connect the check_json_validity function to textChanged signal
        self.targets_input_textarea.textChanged.connect(partial(self.__handle_textarea_json_validity, update_target_list_if_json_defined_is_valid=True))
        self.__handle_textarea_json_validity(update_target_list_if_json_defined_is_valid=True)

        # Create the "Reorder Cards" button
        def user_clicked_reorder_button():
            (json_validity_state, targets_defined, err_desc) = self.__handle_textarea_json_validity(update_target_list_if_json_defined_is_valid=True)
            if json_validity_state == 1:
                ask_to_save_new_targets_to_config(targets_defined)
                self.__handle_textarea_json_validity(update_target_list_if_json_defined_is_valid=True)
                ReorderCardsTab.__execute_reorder_request(self.col, self.target_list)
            elif self.target_list.has_targets() and askUser("Defined targets are not valid.\n\n"+err_desc+"\n\nRestore previously defined targets?"):
                self.targets_input_textarea.setText(self.target_list.dump_json())
            else:
                showWarning("Defined targets are not valid!\n\n"+err_desc)

        exec_reorder_button = QPushButton("Reorder Cards")
        exec_reorder_button.setStyleSheet("font-size: 16px; font-weight: bold; background-color: #23b442; color: white; border:2px solid #23a03e; margin-top:20px;")
        exec_reorder_button.clicked.connect(user_clicked_reorder_button)

        tab_layout.setSpacing(0)
        tab_layout.addWidget(self.targets_input_textarea)
        tab_layout.addWidget(self.targets_input_options_line)
        tab_layout.addWidget(exec_reorder_button)
        tab_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))  # Add an empty spacer row to compress the rows above

    # Check if the JSON and target data in the textarea is valid

    def __handle_textarea_json_validity(self, update_target_list_if_json_defined_is_valid: Boolean) -> Tuple[int, list[ConfigTargetData], str]:

        (json_validity_state, targets_defined, err_desc) = self.target_list.handle_json(self.targets_input_textarea.toPlainText())

        if self.fm_window.addon_config['fm_reorder_target_list'] == targets_defined:
            self.targets_input_reset_button.setDisabled(True)
        else:
            self.targets_input_reset_button.setDisabled(False)

        palette = QPalette()
        if (json_validity_state == 1):  # valid
            palette.setColor(QPalette.ColorRole.Text, QColor("#23b442"))  # Green
            self.targets_input_validation_info_txt_line.setVisible(False)
            if update_target_list_if_json_defined_is_valid:
                self.target_list.set_targets(targets_defined)  # set new targets
            if self.fm_window.addon_config['fm_reorder_target_list'] == targets_defined:
                self.targets_input_save_button.setDisabled(True)
            else:
                self.targets_input_save_button.setDisabled(False)
        else:
            self.targets_input_validation_info_txt_line.setVisible(True)
            self.targets_input_save_button.setDisabled(True)
            self.targets_input_reset_button.setDisabled(False)

        if (json_validity_state == -1):  # invalid json
            palette.setColor(QPalette.ColorRole.Text, QColor("#bb462c"))  # Red

        self.targets_input_textarea.setPalette(palette)
        self.targets_input_validation_info_txt_line.setText(err_desc)

        return (json_validity_state, targets_defined, err_desc)

    # Validation line below textarea, with line of text and buttons on the right

    def __create_targets_input_options_row_widget(self) -> None:

        layout = QHBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # informational text on the left

        self.targets_input_validation_info_txt_line = QLabel("Hello :)")
        self.targets_input_validation_info_txt_line.setStyleSheet("font-weight: bolder; font-size: 13px;")
        self.targets_input_validation_info_txt_line.setVisible(False)
        layout.addWidget(self.targets_input_validation_info_txt_line)

        # reset button

        def user_clicked_reset_button():
            (_, targets_defined, _) = self.target_list.handle_json(self.targets_input_textarea.toPlainText())

            if self.fm_window.addon_config['fm_reorder_target_list'] == targets_defined:
                showInfo("Defined targets are the same as those stored in the configuration!")
                return

            if askUser("Restore targets as they are stored in the configuration?"):
                self.target_list.set_targets(self.fm_window.addon_config['fm_reorder_target_list'])
                json_str = json.dumps(self.fm_window.addon_config['fm_reorder_target_list'], indent=4)
                self.targets_input_textarea.setText(json_str)

        self.targets_input_reset_button = QPushButton("Reset")
        self.targets_input_reset_button.setDisabled(True)
        self.targets_input_reset_button.clicked.connect(user_clicked_reset_button)

        # save button

        def user_clicked_save_button():
            (json_validity_state, targets_defined, _) = self.target_list.handle_json(self.targets_input_textarea.toPlainText())

            if (json_validity_state == 1 and self.fm_window.addon_config['fm_reorder_target_list'] != targets_defined):
                self.fm_window.addon_config['fm_reorder_target_list'] = targets_defined
                self.fm_window.addon_config_write(self.fm_window.addon_config)
                self.targets_input_reset_button.setDisabled(True)

            self.targets_input_save_button.setDisabled(True)

        self.targets_input_save_button = QPushButton("Save")
        self.targets_input_save_button.setDisabled(True)
        self.targets_input_save_button.clicked.connect(user_clicked_save_button)

        layout.addStretch(1)
        layout.addWidget(self.targets_input_reset_button)
        layout.addWidget(self.targets_input_save_button)

        # Set the layout for the QWidget
        self.targets_input_options_line = QWidget()
        self.targets_input_options_line.setLayout(layout)

    @staticmethod
    def __execute_reorder_request(col: Collection, target_list: TargetList):

        if not isinstance(col, Collection):
            showWarning("Collection not found!")
            return

        if not target_list.has_targets():
            showWarning("No targets defined!")
            return

        event_logger = EventLogger()

        (_, warnings) = target_list.reorder_cards(col, event_logger)

        for warning in warnings:
            showWarning(warning)

        var_dump_log(event_logger.events)
