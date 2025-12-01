"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from __future__ import annotations

import json
import re
import shutil
import hashlib
import time
from typing import Optional, Callable, Union, TYPE_CHECKING

from anki.collection import Collection
from aqt.operations import QueryOp

from aqt.utils import askUser, showWarning, showInfo, askUserDialog
from aqt.qt import (
    QWidget, QGridLayout, QLabel, QSpacerItem, QSizePolicy, QPushButton, QApplication,
    Qt, QColor, QPalette, QLayout, QPaintEvent, QTextEdit, pyqtSlot
)


from ..static_lang_data import get_default_wf_list_sources

from .main_window import FrequencyManMainWindow, FrequencyManTab
from .select_new_target_window import SelectNewTargetWindow

from ..lib.event_logger import EventLogger
from ..lib.utilities import ShowResultType, show_result, override

from ..target_list import JSON_TYPE, JsonTargetsValidity, TargetList, TargetListReorderResult, JsonTargetsResult

if TYPE_CHECKING:
    from ..configured_target import ValidConfiguredTarget
    from ..reorder_logger import ReorderLogger
    from ..lib.addon_config import AddonConfig


class TargetsDefiningTextArea(QTextEdit):

    fm_config: AddonConfig
    json_result: Optional[JsonTargetsResult]
    json_interpreter: Callable[[str], JsonTargetsResult]
    on_validity_change_callbacks: list[Callable[[JsonTargetsResult, TargetsDefiningTextArea], None]]
    on_change_callbacks: list[Callable[[JsonTargetsResult, TargetsDefiningTextArea], None]]
    on_first_paint_callbacks: list[Callable[[TargetsDefiningTextArea], None]]
    error_interceptors: list[Callable[[JsonTargetsResult], bool]]

    def __init__(self, parent: QWidget, fm_config: AddonConfig):
        super().__init__(parent)
        self.fm_config = fm_config
        self.setAcceptRichText(False)
        self.setStyleSheet("font-weight: bolder; font-size: 14px; line-height: 1.2; font-family: 'Consolas', 'Courier New', monospace;")
        self.textChanged.connect(self.__handle_content_change)

        self.on_validity_change_callbacks = []
        self.on_change_callbacks = []
        self.on_first_paint_callbacks = []
        self.error_interceptors = []

        self.first_paint_done = False
        self.json_result = None

    @pyqtSlot()
    def __handle_content_change(self):
        self.handle_current_content()

    @override
    def paintEvent(self, e: Optional[QPaintEvent]):
        super().paintEvent(e)
        if not self.first_paint_done:
            self.first_paint_done = True
            for callback in self.on_first_paint_callbacks:
                callback(self)

    def handle_current_content(self, allow_error_interception: int = 5):

        current_content = self.toPlainText()

        new_json_result = self.json_interpreter(current_content)

        if new_json_result.err_desc != "" and allow_error_interception > 0:
            for error_interceptor in self.error_interceptors:
                reload_content = error_interceptor(new_json_result)
                if reload_content:
                    self.handle_current_content(allow_error_interception-1)
                    return

        for callback in self.on_change_callbacks:
            callback(new_json_result, self)

        json_validity_state_has_changed = self.json_result is None or new_json_result.validity_state != self.json_result.validity_state

        if json_validity_state_has_changed:
            for callback in self.on_validity_change_callbacks:
                callback(new_json_result, self)

        self.json_result = new_json_result

    def set_interpreter(self, callback: Callable[[str], JsonTargetsResult]):
        self.json_interpreter = callback

    def on_validity_change(self, callback: Callable[[JsonTargetsResult, TargetsDefiningTextArea], None]):
        self.on_validity_change_callbacks.append(callback)

    def on_change(self, callback: Callable[[JsonTargetsResult, TargetsDefiningTextArea], None]):
        self.on_change_callbacks.append(callback)

    def on_first_paint(self, callback: Callable[[TargetsDefiningTextArea], None]):
        self.on_first_paint_callbacks.append(callback)

    def set_content(self, target_list: Union[list[ValidConfiguredTarget], list[JSON_TYPE], TargetList]):
        if isinstance(target_list, TargetList):
            self.setText(target_list.dump_json())
        elif isinstance(target_list, list):
            dict_target_list: list = []
            for target in target_list:
                if isinstance(target, dict):
                    dict_target_list.append(target)
                else:
                    raise ValueError("Invalid type in target_list!")
            self.setText(json.dumps(dict_target_list, indent=4, ensure_ascii=False))
        else:
            raise ValueError("Invalid target_list type!")

    def add_error_interceptor(self, interceptor: Callable[[JsonTargetsResult], bool]):
        self.error_interceptors.append(interceptor)

    def save_current_to_config(self) -> None:
        if self.json_result is None or self.json_result.valid_targets_defined is None:
            showWarning("Can not save to config because the current list of targets is not valid!")
            return
        self.fm_config.update_setting('reorder_target_list', self.json_result.valid_targets_defined)
        self.handle_current_content()


class ReorderCardsTab(FrequencyManTab):

    id = 'reorder_cards'
    name = 'Reorder cards'

    targets_input_textarea: TargetsDefiningTextArea
    reorder_button: QPushButton
    target_list: TargetList

    fm_config: AddonConfig
    reorder_logger: ReorderLogger

    def __init__(self, fm_config: AddonConfig, fm_window: FrequencyManMainWindow, col: Collection, reorder_logger: ReorderLogger) -> None:

        super().__init__(fm_window, col)
        self.fm_config = fm_config
        self.reorder_logger = reorder_logger

    @override
    def on_tab_first_paint(self, tab_layout: QLayout) -> None:

        self.target_list = self.init_new_target_list()

        # textarea (user can input json to define targets)
        self.targets_input_textarea = self.__create_targets_input_textarea()

        # check errors
        default_wf_lists_dir = self.fm_window.root_dir / 'default_wf_lists'
        language_data_dir = self.language_data.data_dir

        def check_lang_data_id_error(new_json_result: JsonTargetsResult) -> bool:

            match = re.search(r"lang_data_id '([a-zA-Z_]{2,5})'", new_json_result.err_desc)
            if not match:
                return False
            defined_lang_data_id = str(match.group(1)).lower()
            if not defined_lang_data_id in get_default_wf_list_sources():
                return False

            src_file = default_wf_lists_dir / (defined_lang_data_id + '.txt')
            dst_dir = language_data_dir / defined_lang_data_id

            if dst_dir.exists():
                return False

            dst_file = dst_dir / (defined_lang_data_id + '-default.txt')
            if not src_file.is_file():
                return False
            create_default_lang_data_dir = askUser("Language data directory doesn't yet exist for \"{}\".\n\nCreate one and use a default word frequency list?".format(defined_lang_data_id))
            if not create_default_lang_data_dir:
                return False

            if not dst_dir.exists():
                dst_dir.mkdir(parents=True)

            shutil.copyfile(src_file, dst_file)
            return True

        self.targets_input_textarea.add_error_interceptor(check_lang_data_id_error)

        # if no targets defined, refer to 'Add target' button

        def empty_list_error_interceptor(new_json_result: JsonTargetsResult) -> bool:

            if new_json_result.validity_state == JsonTargetsValidity.INVALID_TARGETS and len(new_json_result.targets_defined) == 0 and not self.target_list.has_targets():
                new_json_result.err_desc = "Targets not yet defined. Which cards do you want to reorder? Press the 'Add target' button and define a new target."
            return False

        self.targets_input_textarea.add_error_interceptor(empty_list_error_interceptor)

        # set content

        def set_content_on_first_paint(_):

            # use stored target list (might not be valid, so set as text)
            if "reorder_target_list" in self.fm_config:
                stored_reorder_target_list = self.fm_config['reorder_target_list']
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

    def __create_targets_input_textarea(self) -> TargetsDefiningTextArea:

        targets_input_textarea = TargetsDefiningTextArea(self.fm_window, self.fm_config)
        targets_input_textarea.set_interpreter(lambda json_data: TargetList.get_targets_from_json(json_data, self.col, self.language_data))

        def update_textarea_text_color_by_validity(new_json_result: JsonTargetsResult, targets_input_textarea: TargetsDefiningTextArea):
            palette = QPalette()
            if (new_json_result.validity_state == JsonTargetsValidity.VALID_TARGETS):  # valid
                if self.fm_window.is_dark_mode:
                    palette.setColor(QPalette.ColorRole.Text, QColor("#23b442"))  # Green
                else:
                    palette.setColor(QPalette.ColorRole.Text, QColor("#15842d"))
            if (new_json_result.validity_state == JsonTargetsValidity.INVALID_JSON):  # invalid json
                palette.setColor(QPalette.ColorRole.Text, QColor("#bb462c"))  # Red
            targets_input_textarea.setPalette(palette)

        def update_target_list_if_input_is_valid(new_json_result: JsonTargetsResult, _):
            if (new_json_result.validity_state == JsonTargetsValidity.VALID_TARGETS and new_json_result.valid_targets_defined is not None):
                self.target_list.set_valid_targets(new_json_result.valid_targets_defined)

        targets_input_textarea.on_validity_change(update_textarea_text_color_by_validity)
        targets_input_textarea.on_change(update_target_list_if_input_is_valid)

        return targets_input_textarea

    def __defined_targets_have_changed(self) -> bool:

        if self.targets_input_textarea.json_result is None:
            return False

        stored_target_list = self.fm_config['reorder_target_list'] if 'reorder_target_list' in self.fm_config else None

        if stored_target_list == self.targets_input_textarea.json_result.valid_targets_defined:
            return False

        stored_valid_list = TargetList.validate_target_list(self.fm_config['reorder_target_list'], self.col, self.language_data)[2]
        current_valid_list = TargetList.get_targets_from_json(self.targets_input_textarea.toPlainText(), self.col, self.language_data).valid_targets_defined

        if stored_valid_list and current_valid_list and stored_valid_list == current_valid_list:
            return False  # same when normalized

        return True

    @override
    def on_window_closing(self) -> Optional[int]:
        if not self.first_paint_event_done:
            return
        # empty list
        if self.targets_input_textarea.json_result is None:
            return
        if self.targets_input_textarea.json_result.validity_state is JsonTargetsValidity.INVALID_TARGETS and len(self.targets_input_textarea.json_result.targets_defined) == 0:
            return
        # contains invalid json or invalid targets
        if self.targets_input_textarea.json_result.validity_state is not JsonTargetsValidity.VALID_TARGETS:
            return int(askUserDialog("Unsaved changes will be lost!", buttons=["Ok", "Cancel"], parent=self.fm_window).run() == "Cancel")
        # nothing changed
        if not self.__defined_targets_have_changed():
            return

        # something changed and is valid
        if askUser("Defined targets have changed. Save them to config?"):
            self.targets_input_textarea.save_current_to_config()

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
                # add new target
                current_targets = json_result.targets_defined
                new_targets = current_targets + [dialog.get_selected_target()]
                self.targets_input_textarea.set_content(new_targets)
                # scroll textarea to bottom
                if len(new_targets) > 1 and (vertical_scrollbar := self.targets_input_textarea.verticalScrollBar()) is not None and vertical_scrollbar.isVisible():
                    vertical_scrollbar.setValue(vertical_scrollbar.maximum())

        def update_add_target_button_state(new_json_result: JsonTargetsResult, _):
            # allow if target list is empty or valid
            if len(new_json_result.targets_defined) == 0 and new_json_result.validity_state != JsonTargetsValidity.INVALID_JSON:
                add_target_button.setDisabled(False)
                return
            add_target_button.setDisabled(new_json_result.validity_state != JsonTargetsValidity.VALID_TARGETS or new_json_result.valid_targets_defined is None)

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

        def update_restore_button_state(new_json_result: JsonTargetsResult, targets_input_textarea: TargetsDefiningTextArea):
            if new_json_result.validity_state != JsonTargetsValidity.VALID_TARGETS and self.target_list.has_targets() and self.target_list.dump_json() != targets_input_textarea.toPlainText():
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

            stored_target_list = self.fm_config['reorder_target_list']

            if isinstance(stored_target_list, list) and len(stored_target_list) == 0:
                if askUser("Target list in config is empty. Resetting will result in an empty target list. Continue?"):
                    if askUserDialog("Currently defined targets will be lost!", buttons=["Ok", "Cancel"], parent=self.fm_window).run() == "Ok":
                        self.targets_input_textarea.set_content([])
                return

            json_result = TargetList.get_targets_from_json(self.targets_input_textarea.toPlainText(), self.col, self.language_data)

            if stored_target_list == json_result.targets_defined:
                showInfo("Defined targets are already the same as those stored in the config!")
                return

            if askUser("Reset targets to those stored in the config?"):
                if askUserDialog("Currently defined targets may be lost!", buttons=["Ok", "Cancel"], parent=self.fm_window).run() == "Ok":
                    if isinstance(stored_target_list, list):
                        self.targets_input_textarea.set_content(stored_target_list)

        def update_reset_button_state(current_json_result: JsonTargetsResult, targets_input_textarea: TargetsDefiningTextArea):

            if "reorder_target_list" not in self.fm_config or not isinstance(self.fm_config['reorder_target_list'], list):
                reset_button.setDisabled(True)
                return

            targets_defined_same_as_stored = self.fm_config['reorder_target_list'] == current_json_result.targets_defined
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

            if (json_result.valid_targets_defined is not None and json_result.validity_state == JsonTargetsValidity.VALID_TARGETS and self.fm_config['reorder_target_list'] != json_result.valid_targets_defined):
                self.targets_input_textarea.save_current_to_config()
                reset_button.setDisabled(True)

            save_button.setDisabled(True)

        def update_save_button_state(new_json_result: JsonTargetsResult, targets_input_textarea: TargetsDefiningTextArea):

            if (new_json_result.validity_state == JsonTargetsValidity.VALID_TARGETS and new_json_result.valid_targets_defined is not None):
                if self.fm_config['reorder_target_list'] != new_json_result.valid_targets_defined:
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

        def update_validation_info_txt_line(new_json_result: JsonTargetsResult, _) -> None:
            if (new_json_result.err_desc != ""):
                validation_info_text_line.setVisible(True)
                new_txt = "<style>.alt { font-style: italic; color: gray; }</style>"
                new_txt += new_json_result.err_desc.replace('\n', '<br>')
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
            if "reorder_target_list" not in self.fm_config:
                return
            if not self.__defined_targets_have_changed():
                return
            if askUser("Defined targets have changed. Save them to config?"):
                self.targets_input_textarea.save_current_to_config()

        @pyqtSlot()
        def user_clicked_reorder_button() -> None:
            if self.targets_input_textarea.json_result is None or self.targets_input_textarea.json_result.valid_targets_defined is None:
                showWarning("No valid result found for defined targets!")
            elif not self.targets_input_textarea.json_result.validity_state == JsonTargetsValidity.VALID_TARGETS:
                showWarning("Defined targets are not valid!\n\n"+self.targets_input_textarea.json_result.err_desc)
            else:
                ask_to_save_new_targets_to_config(self.targets_input_textarea.json_result.valid_targets_defined)
                self.__execute_reorder_request()

        normal_style = "QPushButton { font-size: 16px; font-weight: bold; margin-top:20px; margin-bottom:5px; padding-top:5px; padding-bottom:5px; }"
        enabled_style = 'QPushButton:enabled { background-color:#23b442; border:2px solid #23a03e; color:white; }'
        reorder_button.setStyleSheet(normal_style+" "+enabled_style)

        def update_reorder_button_state(new_json_result: JsonTargetsResult, _):
            if self.target_list.has_targets() and new_json_result.validity_state == JsonTargetsValidity.VALID_TARGETS:
                reorder_button.setDisabled(False)
                return
            reorder_button.setDisabled(True)

        reorder_button.clicked.connect(user_clicked_reorder_button)
        self.targets_input_textarea.on_validity_change(update_reorder_button_state)

        return reorder_button

    def __backup_target_list_config(self) -> None:

        json_backup = self.target_list.dump_json()
        hash_hex = hashlib.md5(json_backup.encode('utf-8')).hexdigest()

        backup_dir = self.fm_window.user_files_dir / 'target_list_backups'
        if not backup_dir.is_dir():
            backup_dir.mkdir(parents=True)

        json_backup_file_path = backup_dir / ('target_list_' + hash_hex + '.txt')

        if not json_backup_file_path.exists():
            with json_backup_file_path.open('w', encoding="utf-8") as file:
                # write date and time to file
                file.write("Created on {} at {}.\n\n\n".format(time.strftime("%d-%m-%Y"), time.strftime("%H:%M:%S")))
                file.write(json_backup)
        else:
            json_backup_file_path.touch() # touch file (update access+modification time)

    @staticmethod
    def __get_progress_label(target_index: int, num_targets: int) -> str:
        if num_targets <= 1 or target_index < 0:
            return "Reordering new cards..."

        return "Reordering new cards... ({}/{})".format(target_index+1, num_targets)

    def __execute_reorder_request(self) -> None:

        if not self.target_list.has_targets():
            showWarning("No targets defined!")
            return

        self.__backup_target_list_config()

        if not isinstance(self.col, Collection):
            showWarning("Collection not found!")
            return

        event_logger = EventLogger()

        self.reorder_button.setDisabled(True)

        def reorder_operation(col: Collection) -> TargetListReorderResult:

            reposition_shift_existing = self.fm_config.is_enabled('reposition_shift_existing', True)

            def reorder_status_callback(target_index: int, num_targets: int) -> None:
                def update_progress():
                    if self.fm_window.mw.progress.want_cancel():
                        self.target_list.cancel_reorder()
                    self.fm_window.mw.progress.update(label=self.__get_progress_label(target_index, num_targets))
                self.fm_window.mw.taskman.run_on_main(update_progress)

            reorder_result = self.target_list.reorder_cards(col, event_logger, reorder_status_callback, reposition_shift_existing)

            return reorder_result

        def reorder_show_results(reorder_cards_results: TargetListReorderResult) -> None:

            self.reorder_button.setDisabled(False)

            result_info_str = "Reordering done!"

            num_errors = 0
            for result in reorder_cards_results.reorder_result_list:
                if (result.error is not None):
                    result_info_str += "\n\nError: "+result.error
                    num_errors += 1

            result_info_str += "\n\n"+str(event_logger)

            msg_type: ShowResultType = "warning" if num_errors > 0 else "information"
            if reorder_cards_results.reorder_canceled:
                msg_type = "warning"
            show_result(result_info_str, "Result", msg_type, self.fm_window)
            # showText(result_info_str, self.fm_window, geomKey="ReorderResult")

            if self.fm_config.is_enabled('log_reorder_events'):
                event_logger.append_to_file(self.fm_window.root_dir / 'reorder_events.log')

        def handle_results(reorder_cards_results: TargetListReorderResult) -> None:

            def log_reordering(_: Collection) -> int:
                num_entries_added = self.reorder_logger.log_reordering(self.target_list, reorder_cards_results)
                self.reorder_logger.close()
                return num_entries_added

            def log_reordering_success(num_entries_added: int) -> None:
                if num_entries_added > 0:
                    self.fm_window.mw.deckBrowser.refresh()
                    self.fm_window.mw.toolbar.draw()

            self.reorder_logger.close()
            if not reorder_cards_results.reorder_canceled:
                QueryOp(parent=self.fm_window, op=log_reordering, success=log_reordering_success).run_in_background()

            reorder_show_results(reorder_cards_results)

        shift_pressed = QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier
        ctrl_pressed = QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier
        initial_progress_label = self.__get_progress_label(0, len(self.target_list))

        if shift_pressed and ctrl_pressed:  # for debugging purposes
            handle_results(reorder_operation(self.col))
        else:
            QueryOp(
                parent=self.fm_window,
                op=reorder_operation,
                success=handle_results
            ).with_progress(label=initial_progress_label).run_in_background()
