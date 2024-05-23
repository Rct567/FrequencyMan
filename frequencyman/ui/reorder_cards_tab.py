"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

import json
import re
import shutil
from typing import Any, Optional, Tuple, Callable

from anki.collection import Collection, OpChanges, OpChangesWithCount
from aqt.operations import QueryOp, CollectionOp

from aqt.utils import askUser, showWarning, showInfo, askUserDialog
from aqt import QAction, QSpacerItem, QSizePolicy, QApplication
from aqt.qt import *
from aqt.main import AnkiQt

from ..default_wf_lists import DefaultWordFrequencyLists

from .main_window import FrequencyManMainWindow, FrequencyManTab
from .select_new_target_window import SelectNewTargetWindow

from ..lib.event_logger import EventLogger
from ..lib.utilities import var_dump, var_dump_log

from ..language_data import LanguageData
from ..target import ConfiguredTarget, ValidConfiguredTarget
from ..target_list import JsonTargetsValidity, TargetList, TargetListReorderResult, JsonTargetsResult


class TargetsDefiningTextArea(QTextEdit):

    json_validity_state: Optional[JsonTargetsValidity]
    json_validator: Callable[[str], JsonTargetsResult]
    err_desc: str
    validity_change_callbacks: list[Callable[[JsonTargetsResult, 'TargetsDefiningTextArea'], None]]
    change_callbacks: list[Callable[[JsonTargetsResult, 'TargetsDefiningTextArea'], None]]
    valid_targets_defined: Optional[list[ValidConfiguredTarget]]
    error_interceptors: list[Callable[[JsonTargetsResult], bool]]
    first_paint_callbacks: list[Callable[['TargetsDefiningTextArea'], None]]

    def __init__(self, fm_window: FrequencyManMainWindow):
        super().__init__(fm_window)
        self.fm_window = fm_window
        self.setMinimumHeight(330)
        self.setAcceptRichText(False)
        self.setStyleSheet("font-weight: bolder; font-size: 14px; line-height: 1.2; font-family: 'Consolas', 'Courier New', monospace;")
        self.textChanged.connect(self.__handle_content_change)
        self.validity_change_callbacks = []
        self.change_callbacks = []
        self.first_paint_callbacks = []
        self.error_interceptors = []
        self.json_validity_state = None
        self.valid_targets_defined = None
        self.err_desc = ""
        self.first_paint_done = False

    @pyqtSlot()
    def __handle_content_change(self):
        self.handle_current_content()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.first_paint_done:
            self.first_paint_done = True
            self.__call_first_paint_listeners()

    def handle_current_content(self, allow_error_interception=5):

        current_content = self.toPlainText()

        json_result = self.json_validator(current_content)

        if json_result.err_desc != "" and allow_error_interception > 0:
            for error_interceptor in self.error_interceptors:
                reload_content = error_interceptor(json_result)
                if reload_content:
                    self.handle_current_content(allow_error_interception-1)
                    return

        json_validity_state_has_changed = json_result.validity_state != self.json_validity_state
        self.json_validity_state = json_result.validity_state
        self.err_desc = json_result.err_desc
        if (json_result.validity_state == JsonTargetsValidity.VALID_TARGETS):
            self.valid_targets_defined = json_result.valid_targets_defined
        self.__call_change_listeners(json_result)
        if json_validity_state_has_changed:
            self.__call_validity_change_listeners(json_result)

    def __call_validity_change_listeners(self, json_result: JsonTargetsResult):
        for callback in self.validity_change_callbacks:
            callback(json_result, self)

    def __call_change_listeners(self, json_result: JsonTargetsResult):
        for callback in self.change_callbacks:
            callback(json_result, self)

    def __call_first_paint_listeners(self):
        for callback in self.first_paint_callbacks:
            callback(self)

    def set_validator(self, callback: Callable[[str], JsonTargetsResult]):
        self.json_validator = callback

    def on_validity_change(self, callback: Callable[[JsonTargetsResult, 'TargetsDefiningTextArea'], None]):
        self.validity_change_callbacks.append(callback)

    def on_change(self, callback: Callable[[JsonTargetsResult, 'TargetsDefiningTextArea'], None]):
        self.change_callbacks.append(callback)

    def on_first_paint(self, callback: Callable[['TargetsDefiningTextArea'], None]):
        self.first_paint_callbacks.append(callback)

    def set_content(self, target_list: Union[list[ConfiguredTarget], list[dict[str, Any]], TargetList]):
        if isinstance(target_list, TargetList):
            self.setText(target_list.dump_json())
        elif isinstance(target_list, list):
            dict_target_list: list[dict] = []
            for target in target_list:
                if isinstance(target, ConfiguredTarget):
                    dict_target_list.append(dict(target.data))
                elif isinstance(target, dict):
                    dict_target_list.append(target)
                else:
                    raise ValueError("Invalid type in target_list!")
            self.setText(json.dumps(dict_target_list, indent=4))
        else:
            raise ValueError("Invalid target_list type!")

    def add_error_interceptor(self, interceptor: Callable[[JsonTargetsResult], bool]):
        self.error_interceptors.append(interceptor)


class ReorderCardsTab(FrequencyManTab):

    fm_window: FrequencyManMainWindow
    col: Collection
    target_list: TargetList
    language_data: LanguageData

    targets_input_textarea: TargetsDefiningTextArea
    reorder_button: QPushButton

    def __init__(self, fm_window: FrequencyManMainWindow, col: Collection) -> None:

        super().__init__(fm_window)

        self.id = 'reorder_cards'
        self.name = 'Reorder cards'

        self.fm_window = fm_window
        self.col = col

    def on_tab_painted(self, tab_layout: QLayout):

        # language data
        lang_data_dir = os.path.join(self.fm_window.user_files_dir, 'lang_data')
        if not os.path.isdir(lang_data_dir):
            os.makedirs(lang_data_dir)

        self.language_data = LanguageData(lang_data_dir)

        # target data (list of targets for reordering)
        self.target_list = TargetList(self.language_data, self.col)

        # textarea (user can input json to define targets)
        self.targets_input_textarea = self.__create_targets_input_textarea()

        # check errors
        default_wf_lists_dir = os.path.join(self.fm_window.root_dir, 'default_wf_lists')
        language_data_dir = self.language_data.data_dir

        def check_lang_data_id_error(json_result: JsonTargetsResult) -> bool:

            match = re.search(r"lang_data_id '([a-zA-Z_]{2,5})'", json_result.err_desc)
            if not match:
                return False
            defined_lang_data_id = str(match.group(1)).lower()
            if not defined_lang_data_id in DefaultWordFrequencyLists.default_wf_lists:
                return False

            src_file = os.path.join(default_wf_lists_dir, defined_lang_data_id+'.txt')
            dst_dir = os.path.join(language_data_dir, defined_lang_data_id)
            dst_file = os.path.join(dst_dir, defined_lang_data_id+'-default.txt')
            if not os.path.isfile(src_file):
                return False
            create_default_lang_data_dir = askUser("Language data directory doesn't yet exist for \"{}\".\n\nCreate one and use a default word frequency list?".format(defined_lang_data_id))
            if not create_default_lang_data_dir:
                return False

            if not os.path.exists(dst_dir):
                os.makedirs(dst_dir)

            shutil.copyfile(src_file, dst_file)
            return True

        self.targets_input_textarea.add_error_interceptor(check_lang_data_id_error)

        # if no targets defined, refer to 'Add target' button

        def empty_list_error_interceptor(json_result: JsonTargetsResult) -> bool:

            if json_result.validity_state == JsonTargetsValidity.INVALID_TARGETS and len(json_result.targets_defined) == 0 and not self.target_list.has_targets():
                json_result.err_desc = "Targets not yet defined. Which cards do you want to reorder? Press the 'Add target' button and define a new target."
            return False

        self.targets_input_textarea.add_error_interceptor(empty_list_error_interceptor)

        # set content

        def set_content_on_first_paint(_):

            # use stored target list (might not be valid, so set as text)
            if self.fm_window.addon_config and "reorder_target_list" in self.fm_window.addon_config:
                stored_reorder_target_list = self.fm_window.addon_config.get("reorder_target_list")
                if isinstance(stored_reorder_target_list, list):
                    self.targets_input_textarea.set_content(stored_reorder_target_list)

            # Textarea widget
            if (self.target_list.has_targets()):
                self.targets_input_textarea.set_content(self.target_list)
            elif self.targets_input_textarea.toPlainText() == "":  # when does this even happen?
                self.targets_input_textarea.set_content([])

        self.targets_input_textarea.on_first_paint(set_content_on_first_paint)

        # reorder button

        self.reorder_button = self.__create_reorder_button()

        # set tab layout and add widgets

        tab_layout.setSpacing(0)
        tab_layout.addWidget(self.targets_input_textarea)
        tab_layout.addWidget(self.__create_targets_input_options_row_widget())
        tab_layout.addWidget(self.__create_targets_input_validation_info_row_widget())
        tab_layout.addWidget(self.reorder_button)
        tab_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))  # Add an empty spacer row to compress the rows above

    def __create_targets_input_textarea(self) -> TargetsDefiningTextArea:

        targets_input_textarea = TargetsDefiningTextArea(self.fm_window)
        targets_input_textarea.set_validator(lambda json_data: TargetList.get_targets_from_json(json_data, self.col, self.language_data))

        def update_textarea_text_color_by_validity(json_result: JsonTargetsResult, targets_input_textarea: TargetsDefiningTextArea):
            palette = QPalette()
            if (json_result.validity_state == JsonTargetsValidity.VALID_TARGETS):  # valid
                if self.fm_window.is_dark_mode:
                    palette.setColor(QPalette.ColorRole.Text, QColor("#23b442"))  # Green
                else:
                    palette.setColor(QPalette.ColorRole.Text, QColor("#15842d"))
            if (json_result.validity_state == JsonTargetsValidity.INVALID_JSON):  # invalid json
                palette.setColor(QPalette.ColorRole.Text, QColor("#bb462c"))  # Red
            targets_input_textarea.setPalette(palette)

        def update_target_list_if_input_is_valid(json_result: JsonTargetsResult, targets_input_textarea: TargetsDefiningTextArea):
            if (json_result.validity_state == JsonTargetsValidity.VALID_TARGETS and targets_input_textarea.valid_targets_defined):
                self.target_list.set_valid_targets(targets_input_textarea.valid_targets_defined)

        targets_input_textarea.on_validity_change(update_textarea_text_color_by_validity)
        targets_input_textarea.on_change(update_target_list_if_input_is_valid)

        return targets_input_textarea

    def __create_targets_input_options_row_widget(self) -> QWidget:

        # add target button

        @pyqtSlot()
        def user_clicked_add_target_button():
            json_result = TargetList.get_targets_from_json(self.targets_input_textarea.toPlainText(), self.col, self.language_data)
            if json_result.validity_state == JsonTargetsValidity.INVALID_JSON:
                showWarning(json_result.err_desc)
                return

            dialog = SelectNewTargetWindow(self.fm_window, self.col)
            if dialog.exec():
                new_targets = json_result.targets_defined + [dialog.get_selected_target()]
                self.targets_input_textarea.set_content(new_targets)

        def update_add_target_button_state(json_result: JsonTargetsResult, targets_input_textarea: TargetsDefiningTextArea):
            add_target_button.setDisabled(self.target_list.has_targets() and json_result.validity_state == JsonTargetsValidity.INVALID_JSON)

        add_target_button = QPushButton("Add target")
        add_target_button.setToolTip("Add a new target to the list.")
        add_target_button.setDisabled(True)
        add_target_button.clicked.connect(user_clicked_add_target_button)
        self.targets_input_textarea.on_change(update_add_target_button_state)

        # restore button

        @pyqtSlot()
        def user_clicked_restore_button():
            if askUser("Restore to last validly defined targets?"):
                self.targets_input_textarea.set_content(self.target_list)

        def update_restore_button_state(json_result: JsonTargetsResult, targets_input_textarea: TargetsDefiningTextArea):
            if json_result.validity_state != JsonTargetsValidity.VALID_TARGETS and self.target_list.has_targets() and self.target_list.dump_json() != targets_input_textarea.toPlainText():
                restore_button.setVisible(True)
                return
            restore_button.setVisible(False)

        restore_button = QPushButton("Restore")
        restore_button.setToolTip("Restore to last validly defined targets.")
        restore_button.clicked.connect(user_clicked_restore_button)
        self.targets_input_textarea.on_change(update_restore_button_state)

        # reset button

        @pyqtSlot()
        def user_clicked_reset_button():

            if len(self.fm_window.addon_config['reorder_target_list']) == 0:
                if askUser("Target list in config is empty. Resetting will result in an empty target list. Continue?"):
                    if askUserDialog("Currently defined targets will be lost!", buttons=["Ok", "Cancel"]).exec() == 0:
                        self.targets_input_textarea.set_content([])
                return

            json_result = TargetList.get_targets_from_json(self.targets_input_textarea.toPlainText(), self.col, self.language_data)

            if self.fm_window.addon_config['reorder_target_list'] == json_result.targets_defined:
                showInfo("Defined targets are already the same as those stored in the config!")
                return

            if askUser("Reset targets to those stored in the config?"):
                if askUserDialog("Currently defined targets may be lost.", buttons=["Ok", "Cancel"]).exec() == 0:
                    stored_target_list = self.fm_window.addon_config['reorder_target_list']
                    self.targets_input_textarea.set_content(stored_target_list)

        def update_reset_button_state(json_result: JsonTargetsResult, targets_input_textarea: TargetsDefiningTextArea):

            if "reorder_target_list" not in self.fm_window.addon_config or not isinstance(self.fm_window.addon_config['reorder_target_list'], list):
                reset_button.setDisabled(True)
                return

            json_result = TargetList.get_targets_from_json(self.targets_input_textarea.toPlainText(), self.col, self.language_data)
            targets_defined_same_as_stored = self.fm_window.addon_config['reorder_target_list'] == json_result.targets_defined
            reset_button.setDisabled(targets_defined_same_as_stored)

        reset_button = QPushButton("Reset")
        reset_button.setToolTip("Reset to targets stored in the config.")
        reset_button.setDisabled(True)
        reset_button.clicked.connect(user_clicked_reset_button)
        self.targets_input_textarea.on_change(update_reset_button_state)

        # save button

        @pyqtSlot()
        def user_clicked_save_button():
            json_result = TargetList.get_targets_from_json(self.targets_input_textarea.toPlainText(), self.col, self.language_data)

            if (json_result.valid_targets_defined is not None and json_result.validity_state == JsonTargetsValidity.VALID_TARGETS and self.fm_window.addon_config['reorder_target_list'] != json_result.valid_targets_defined):
                self.fm_window.addon_config['reorder_target_list'] = [target.data for target in json_result.valid_targets_defined]
                self.fm_window.addon_config_write(self.fm_window.addon_config)
                reset_button.setDisabled(True)

            save_button.setDisabled(True)

        def update_save_button_state(json_result: JsonTargetsResult, targets_input_textarea: TargetsDefiningTextArea):

            if (json_result.validity_state == JsonTargetsValidity.VALID_TARGETS):
                if self.fm_window.addon_config['reorder_target_list'] != targets_input_textarea.valid_targets_defined:
                    save_button.setDisabled(False)
                    return
            save_button.setDisabled(True)

        save_button = QPushButton("Save")
        save_button.setToolTip("Save targets to config.")
        save_button.setDisabled(True)
        save_button.clicked.connect(user_clicked_save_button)
        self.targets_input_textarea.on_change(update_save_button_state)

        # set layout

        grid_layout = QGridLayout()

        grid_layout.addWidget(add_target_button, 0, 0, 1, 1, alignment=Qt.AlignmentFlag.AlignTop)
        grid_layout.setColumnStretch(1, 1)
        spacer_item = QSpacerItem(12, 12, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        grid_layout.addItem(spacer_item, 0, 1, 1, 1)

        grid_layout.addWidget(restore_button, 0, 2, 1, 1, alignment=Qt.AlignmentFlag.AlignTop)
        grid_layout.addWidget(reset_button, 0, 3, 1, 1, alignment=Qt.AlignmentFlag.AlignTop)
        grid_layout.addWidget(save_button, 0, 4, 1, 1, alignment=Qt.AlignmentFlag.AlignTop)

        # set widget with grid
        targets_input_options_line = QWidget()
        targets_input_options_line.setLayout(grid_layout)
        return targets_input_options_line

    def __create_targets_input_validation_info_row_widget(self) -> QWidget:

        validation_info_text_line = QLabel()
        validation_info_text_line.setTextFormat(Qt.TextFormat.RichText)
        validation_info_text_line.setStyleSheet("font-weight: bolder; font-size: 13px; margin-top:8px;")
        validation_info_text_line.setWordWrap(True)

        def update_validation_info_txt_line(_, targets_input_textarea: TargetsDefiningTextArea):
            if (targets_input_textarea.err_desc != ""):
                validation_info_text_line.setVisible(True)
                new_txt = "<style>.alt { font-style: italic; color: gray; }</style>"
                new_txt += targets_input_textarea.err_desc.replace('\n', '<br>')
                validation_info_text_line.setText(new_txt)
            else:
                validation_info_text_line.setVisible(False)

        self.targets_input_textarea.on_change(update_validation_info_txt_line)

        return validation_info_text_line

    def __create_reorder_button(self) -> QPushButton:

        reorder_button = QPushButton("Reorder Cards")
        reorder_button.setDisabled(True)

        # user clicked reorder... ask to save to config if new targets have been defined

        def ask_to_save_new_targets_to_config(targets_defined: list[ValidConfiguredTarget]):
            if self.fm_window.addon_config is None or "reorder_target_list" not in self.fm_window.addon_config:
                return
            if self.fm_window.addon_config['reorder_target_list'] == targets_defined:
                return
            if askUser("Defined targets have changed. Save them to config?"):
                self.fm_window.addon_config['reorder_target_list'] = [target.data for target in targets_defined]
                self.fm_window.addon_config_write(self.fm_window.addon_config)
                self.targets_input_textarea.handle_current_content()

        def user_clicked_reorder_button():
            if self.targets_input_textarea.json_validity_state == JsonTargetsValidity.VALID_TARGETS and self.targets_input_textarea.valid_targets_defined:
                ask_to_save_new_targets_to_config(self.targets_input_textarea.valid_targets_defined)
                self.__execute_reorder_request()
            else:
                showWarning("Defined targets are not valid!\n\n"+self.targets_input_textarea.err_desc)

        normal_style = "QPushButton { font-size: 16px; font-weight: bold; margin-top:15px; }"
        disabled_style = 'QPushButton:enabled { background-color:#23b442; border:2px solid #23a03e; color:white; }'
        reorder_button.setStyleSheet(normal_style+" "+disabled_style)

        def update_reorder_button_state(json_result: JsonTargetsResult, _):
            if self.target_list.has_targets() and json_result.validity_state == JsonTargetsValidity.VALID_TARGETS:
                reorder_button.setDisabled(False)
                return
            reorder_button.setDisabled(True)

        reorder_button.clicked.connect(user_clicked_reorder_button)
        self.targets_input_textarea.on_validity_change(update_reorder_button_state)

        return reorder_button

    def __execute_reorder_request(self):

        if not isinstance(self.col, Collection):
            showWarning("Collection not found!")
            return

        if not self.target_list.has_targets():
            showWarning("No targets defined!")
            return

        event_logger = EventLogger()

        self.reorder_button.setDisabled(True)

        def reorder_operation(col: Collection) -> TargetListReorderResult:

            nonlocal ctrl_pressed
            schedule_cards_as_new = bool(ctrl_pressed)

            return self.target_list.reorder_cards(col, event_logger, schedule_cards_as_new)

        def reorder_show_results(reorder_cards_results: TargetListReorderResult):

            self.reorder_button.setDisabled(False)

            result_info_str = "Reordering done!"

            num_errors = 0
            for result in reorder_cards_results.reorder_result_list:
                if (result.error is not None):
                    result_info_str += "\n\nError: "+result.error
                    num_errors += 1

            result_info_str += "\n\n"+str(event_logger)

            if num_errors > 0:
                showWarning(result_info_str)
            else:
                showInfo(result_info_str)

            if self.fm_window.addon_config.get('log_reorder_events', False):
                event_logger.append_to_file(os.path.join(self.fm_window.root_dir, 'reorder_events.log'))

        shift_pressed = QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier
        ctrl_pressed = QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier

        if shift_pressed and ctrl_pressed:  # for debugging purposes
            reorder_show_results(reorder_operation(self.col))
        else:
            QueryOp(
                parent=self.fm_window,
                op=reorder_operation,
                success=reorder_show_results
            ).with_progress(label="Reordering new cards...").run_in_background()
