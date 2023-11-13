from enum import Enum
import json
from time import sleep
from typing import Optional, Tuple

from anki.collection import Collection, OpChanges, OpChangesWithCount
from aqt.operations import QueryOp, CollectionOp

from aqt.utils import askUser, showWarning, showInfo
from aqt import QAction, QSpacerItem, QSizePolicy
from aqt.qt import *
from aqt.main import AnkiQt

from .main_window import FrequencyManMainWindow

from ..lib.event_logger import EventLogger
from ..lib.utilities import var_dump, var_dump_log

from ..target import ConfigTargetDataNotes, TargetReorderResult
from ..word_frequency_list import WordFrequencyLists
from ..target_list import ConfigTargetData, TargetList, TargetListReorderResult


class TargetsDefiningTextArea(QTextEdit):

    json_validity_state: int
    json_validator: Callable[[str], Tuple[int, list[ConfigTargetData], str]]
    err_desc: str
    validity_change_callbacks: list[Callable[[int, 'TargetsDefiningTextArea'], None]]
    change_callbacks: list[Callable[[int, 'TargetsDefiningTextArea'], None]]
    targets_defined: list[ConfigTargetData]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(300)
        self.setAcceptRichText(False)
        self.setStyleSheet("font-weight: bolder; font-size: 14px; line-height: 1.2;")
        self.textChanged.connect(self.__handle_content_change)
        self.validity_change_callbacks = []
        self.change_callbacks = []
        self.json_validity_state = 0

    @pyqtSlot()
    def __handle_content_change(self):
        self.handle_current_content()

    def handle_current_content(self):
        input_json_txt: str = self.toPlainText()
        (new_json_validity_state, new_targets_defined, new_err_desc) = self.json_validator(input_json_txt)
        json_validity_state_has_changed = new_json_validity_state != self.json_validity_state
        self.json_validity_state = new_json_validity_state
        self.err_desc = new_err_desc
        if (new_json_validity_state == 1):
            self.targets_defined = new_targets_defined
        self.__call_change_listeners(new_json_validity_state)
        if json_validity_state_has_changed:
            self.__call_validity_change_listeners(new_json_validity_state)

    def __call_validity_change_listeners(self, json_validity_state: int):
        for callback in self.validity_change_callbacks:
            callback(json_validity_state, self)

    def __call_change_listeners(self, json_validity_state: int):
        for callback in self.change_callbacks:
            callback(json_validity_state, self)

    def set_validator(self, callback: Callable):
        self.json_validator = callback

    def on_validity_change(self, callback: Callable[[int, 'TargetsDefiningTextArea'], None]):
        self.validity_change_callbacks.append(callback)

    def on_change(self, callback: Callable[[int, 'TargetsDefiningTextArea'], None]):
        self.change_callbacks.append(callback)

    def set_target_list(self, target_list: TargetList):
        self.setText(target_list.dump_json())


class ReorderCardsTab:

    fm_window: FrequencyManMainWindow
    col: Collection
    target_list: TargetList

    targets_input_textarea: TargetsDefiningTextArea
    targets_input_options_line: QWidget
    targets_input_validation_info_txt_line: QLabel
    targets_input_restore_button: QPushButton
    targets_input_reset_button: QPushButton
    targets_input_save_button: QPushButton
    exec_reorder_button: QPushButton

    def __init__(self, fm_window: FrequencyManMainWindow, col: Collection) -> None:

        self.fm_window = fm_window
        self.col = col

        # word frequency lists can be used for all targets
        frequency_lists_dir = os.path.join(self.fm_window.root_dir, 'user_files', 'frequency_lists')
        word_frequency_lists = WordFrequencyLists(frequency_lists_dir)

        # target data (list of targets for reordering)
        self.target_list = TargetList(word_frequency_lists)
        if self.fm_window.addon_config and "fm_reorder_target_list" in self.fm_window.addon_config:
            self.target_list.set_targets(self.fm_window.addon_config.get("fm_reorder_target_list", []))

        # textarea (user can input json to define targets)
        self.targets_input_textarea = TargetsDefiningTextArea()
        self.targets_input_textarea.set_validator(self.target_list.handle_json)

        def update_textarea_text_color_by_validity(json_validity_state, targets_input_textarea: TargetsDefiningTextArea):
            palette = QPalette()
            if (json_validity_state == 1):  # valid
                palette.setColor(QPalette.ColorRole.Text, QColor("#23b442"))  # Green
            if (json_validity_state == -1):  # invalid json
                palette.setColor(QPalette.ColorRole.Text, QColor("#bb462c"))  # Red
            targets_input_textarea.setPalette(palette)

        def update_target_list_if_input_is_valid(json_validity_state, targets_input_textarea: TargetsDefiningTextArea):
            if (json_validity_state == 1):
                self.target_list.set_targets(targets_input_textarea.targets_defined)

        self.targets_input_textarea.on_validity_change(update_textarea_text_color_by_validity)
        self.targets_input_textarea.on_change(update_target_list_if_input_is_valid)

        # row below textarea
        self.__create_targets_input_options_row_widget()

    def create_new_tab(self):

        # Create a new tab and its layout
        (tab_layout, tab) = self.fm_window.create_new_tab('reorder_cards', "Reorder cards")

        # Textarea widget
        if (self.target_list.has_targets()):
            self.targets_input_textarea.set_target_list(self.target_list)
        else:  # when does this even happen?
            example_data_notes_item: ConfigTargetDataNotes = {'name': '** name of notes type **', 'fields': {"Front": "JP", "Back": "EN"}}
            example_target: ConfigTargetData = {'deck': '** name of main deck **', 'notes': [example_data_notes_item]}
            example_target_list = [example_target]
            self.targets_input_textarea.setText(json.dumps(example_target_list, indent=4))

        # user clicked reorder... ask to save to config if new targets have been defined

        def ask_to_save_new_targets_to_config(targets_defined: list[ConfigTargetData]):
            if self.fm_window.addon_config is None or "fm_reorder_target_list" not in self.fm_window.addon_config:
                return
            if self.fm_window.addon_config['fm_reorder_target_list'] == targets_defined:
                return
            if askUser("Defined targets have changed. Save them to config?"):
                self.fm_window.addon_config['fm_reorder_target_list'] = targets_defined
                self.fm_window.addon_config_write(self.fm_window.addon_config)
                self.targets_input_textarea.handle_current_content()

        # reorder button

        self.exec_reorder_button = QPushButton("Reorder Cards")

        def user_clicked_reorder_button():
            if self.targets_input_textarea.json_validity_state == 1:
                ask_to_save_new_targets_to_config(self.targets_input_textarea.targets_defined)
                self.__execute_reorder_request()
            else:
                showWarning("Defined targets are not valid!\n\n"+self.targets_input_textarea.err_desc)

        normal_style = "QPushButton { font-size: 16px; font-weight: bold; color: white; margin-top:20px; background-color: #23b442; color: white; border:2px solid #23a03e; }"
        disabled_style = 'QPushButton:disabled { background-color:#7e5348 ; border-color:#6c4338; color:#bcaca7 }'
        self.exec_reorder_button.setStyleSheet(normal_style+" "+disabled_style)

        def update_reorder_button_state(json_validity_state, _):
            if self.target_list.has_targets() and json_validity_state == 1:
                self.exec_reorder_button.setDisabled(False)
                return
            self.exec_reorder_button.setDisabled(True)

        self.exec_reorder_button.clicked.connect(user_clicked_reorder_button)
        self.targets_input_textarea.on_validity_change(update_reorder_button_state)

        tab_layout.setSpacing(0)
        tab_layout.addWidget(self.targets_input_textarea)
        tab_layout.addWidget(self.targets_input_options_line)
        tab_layout.addWidget(self.exec_reorder_button)
        tab_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))  # Add an empty spacer row to compress the rows above

    # Validation line below textarea, with line of text on the left and buttons on the right

    def __create_targets_input_options_row_widget(self) -> None:

        # informational text on the left

        self.targets_input_validation_info_txt_line = QLabel("Hello :)")
        self.targets_input_validation_info_txt_line.setStyleSheet("font-weight: bolder; font-size: 13px;")
        self.targets_input_validation_info_txt_line.setWordWrap(True)

        def update_validation_info_txt_line(json_validity_state, targets_input_textarea: TargetsDefiningTextArea):
            if (targets_input_textarea.err_desc != ""):
                self.targets_input_validation_info_txt_line.setVisible(True)
                self.targets_input_validation_info_txt_line.setText(targets_input_textarea.err_desc)
            else:
                self.targets_input_validation_info_txt_line.setVisible(False)

        self.targets_input_textarea.on_validity_change(update_validation_info_txt_line)

        # restore button

        @pyqtSlot()
        def user_clicked_restore_button():
            if askUser("Restore previously defined targets?"):
                self.targets_input_textarea.setText(self.target_list.dump_json())

        def update_restore_button_state(json_validity_state, targets_input_textarea: TargetsDefiningTextArea):
            if json_validity_state != 1 and self.target_list.has_targets() and self.target_list.dump_json() != targets_input_textarea.toPlainText():
                self.targets_input_restore_button.setVisible(True)
                return
            self.targets_input_restore_button.setVisible(False)

        self.targets_input_restore_button = QPushButton("Restore")
        self.targets_input_restore_button.clicked.connect(user_clicked_restore_button)
        self.targets_input_textarea.on_change(update_restore_button_state)

        # reset button

        @pyqtSlot()
        def user_clicked_reset_button():
            (_, targets_defined, _) = self.target_list.handle_json(self.targets_input_textarea.toPlainText())

            if self.fm_window.addon_config['fm_reorder_target_list'] == targets_defined:
                showInfo("Defined targets are the same as those stored in the configuration!")
                return

            if askUser("Restore targets as they are stored in the configuration?"):
                self.target_list.set_targets(self.fm_window.addon_config['fm_reorder_target_list'])
                json_str = json.dumps(self.fm_window.addon_config['fm_reorder_target_list'], indent=4)
                self.targets_input_textarea.setText(json_str)

        def update_reset_button_state(json_validity_state, targets_input_textarea: TargetsDefiningTextArea):
            if json_validity_state == 1 and self.fm_window.addon_config['fm_reorder_target_list'] == targets_input_textarea.targets_defined:
                self.targets_input_reset_button.setDisabled(True)
            else:
                self.targets_input_reset_button.setDisabled(False)

        self.targets_input_reset_button = QPushButton("Reset")
        self.targets_input_reset_button.setDisabled(True)
        self.targets_input_reset_button.clicked.connect(user_clicked_reset_button)
        self.targets_input_textarea.on_change(update_reset_button_state)

        # save button

        @pyqtSlot()
        def user_clicked_save_button():
            (json_validity_state, targets_defined, _) = self.target_list.handle_json(self.targets_input_textarea.toPlainText())

            if (json_validity_state == 1 and self.fm_window.addon_config['fm_reorder_target_list'] != targets_defined):
                self.fm_window.addon_config['fm_reorder_target_list'] = targets_defined
                self.fm_window.addon_config_write(self.fm_window.addon_config)
                self.targets_input_reset_button.setDisabled(True)

            self.targets_input_save_button.setDisabled(True)

        def update_save_button_state(json_validity_state, targets_input_textarea: TargetsDefiningTextArea):

            if (json_validity_state == 1):
                if self.fm_window.addon_config['fm_reorder_target_list'] != targets_input_textarea.targets_defined:
                    self.targets_input_save_button.setDisabled(False)
                    return
            self.targets_input_save_button.setDisabled(True)

        self.targets_input_save_button = QPushButton("Save")
        self.targets_input_save_button.setDisabled(True)
        self.targets_input_save_button.clicked.connect(user_clicked_save_button)
        self.targets_input_textarea.on_change(update_save_button_state)

        # set layout

        grid_layout = QGridLayout()
        grid_layout.addWidget(self.targets_input_validation_info_txt_line, 0, 0, 1, 1)
        grid_layout.setColumnStretch(0, 1)
        spacer_item = QSpacerItem(12, 12, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        grid_layout.addItem(spacer_item, 0, 1, 1, 1)

        grid_layout.addWidget(self.targets_input_restore_button, 0, 2, 1, 1, alignment=Qt.AlignmentFlag.AlignTop)
        grid_layout.addWidget(self.targets_input_reset_button, 0, 3, 1, 1, alignment=Qt.AlignmentFlag.AlignTop)
        grid_layout.addWidget(self.targets_input_save_button, 0, 4, 1, 1, alignment=Qt.AlignmentFlag.AlignTop)

        # set widget with grid
        self.targets_input_options_line = QWidget()
        self.targets_input_options_line.setLayout(grid_layout)

    def __execute_reorder_request(self):

        if not isinstance(self.col, Collection):
            showWarning("Collection not found!")
            return

        if not self.target_list.has_targets():
            showWarning("No targets defined!")
            return

        event_logger = EventLogger()

        self.exec_reorder_button.setDisabled(True)

        self.reorder_cards_results: TargetListReorderResult

        def anki_collection_operation(collection) -> Union[OpChanges, OpChangesWithCount]:
            # reorder cards in target list
            self.reorder_cards_results = self.target_list.reorder_cards(collection, event_logger)

            if (self.reorder_cards_results.update_notes_anki_op_changes is not None):
                return self.reorder_cards_results.update_notes_anki_op_changes
            elif (self.reorder_cards_results.repositioning_anki_op_changes):
                return self.reorder_cards_results.repositioning_anki_op_changes
            else:
                return OpChangesWithCount(count=0)

        def anki_collection_operation_success(op_result: Union[OpChanges, OpChangesWithCount]):

            self.exec_reorder_button.setDisabled(False)

            result_info_str = "Reordering done!"

            num_errors = 0
            for result in self.reorder_cards_results.reorder_result_list:
                if (result.error is not None):
                    result_info_str += "\n\nError: "+result.error
                    num_errors += 1

            result_info_str += "\n\n"+str(event_logger)

            if num_errors > 0:
                showWarning(result_info_str)
            else:
                showInfo(result_info_str)

            if (self.fm_window.addon_config.get('log_reorder_events', 'false') == 'true'):
                event_logger.append_to_file(os.path.join(self.fm_window.root_dir, 'reorder_events.log'))

        CollectionOp(
            parent=self.fm_window,
            op=anki_collection_operation
        ).success(anki_collection_operation_success).run_in_background()
