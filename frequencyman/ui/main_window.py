"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from functools import cached_property
import os
from typing import Collection, Optional, Union

from ..language_data import LanguageData
from ..target_list import TargetList

from ..lib.persistent_cacher import PersistentCacher
from ..lib.addon_config import AddonConfig
from ..lib.utilities import var_dump_log, override

from aqt.qt import QWidget, QVBoxLayout, QLayout, QPaintEvent, QCloseEvent, QDialog, QTabWidget
from aqt.main import AnkiQt

from anki.collection import Collection

try:
    from ..version import FREQUENCYMAN_VERSION
    fm_version = FREQUENCYMAN_VERSION
except ImportError:
    fm_version = ""


class FrequencyManTab(QWidget):

    id: str
    name: str
    first_paint_done: bool
    col: Collection
    fm_window: 'FrequencyManMainWindow'

    def __init__(self, parent: 'FrequencyManMainWindow', col: Collection):
        super().__init__(parent)
        self.first_paint_done = False
        self.col = col
        self.fm_window = parent

    def on_tab_created(self, tab_layout: QVBoxLayout):
        pass

    def on_tab_painted(self, tab_layout: QLayout):
        pass

    def on_window_closing(self) -> Optional[int]:
        pass

    @cached_property
    def language_data(self) -> LanguageData:

        lang_data_dir = os.path.join(self.fm_window.user_files_dir, 'lang_data')
        if not os.path.isdir(lang_data_dir):
            os.makedirs(lang_data_dir)

        return LanguageData(lang_data_dir)

    @cached_property
    def cacher(self) -> PersistentCacher:

        return PersistentCacher(os.path.join(self.fm_window.user_files_dir, 'cacher_data.sqlite'))

    def init_new_target_list(self) -> TargetList:
        
        return TargetList(self.language_data, self.cacher, self.col)

    @override
    def paintEvent(self, a0: Optional[QPaintEvent]):
        if not self.first_paint_done and (layout := self.layout()) is not None:
            self.first_paint_done = True
            self.on_tab_painted(layout)


# FrequencyMan Main Window class

class FrequencyManMainWindow(QDialog):

    root_dir: str
    user_files_dir: str

    mw: AnkiQt
    fm_config: AddonConfig
    is_dark_mode: bool

    tab_menu_options: dict[str, QWidget]

    def __init__(self, mw: AnkiQt, fm_config: AddonConfig, root_dir: str, user_files_dir: str):

        super().__init__(mw)
        self.mw = mw
        self.fm_config = fm_config
        self.is_dark_mode = mw.app.styleSheet().lower().find("dark") != -1

        if fm_version != "":
            self.setWindowTitle("FrequencyMan v"+fm_version)
        else:
            self.setWindowTitle("FrequencyMan")

        self.setMinimumSize(650, 600)

        # Create a tab widget
        self.tab_widget = QTabWidget()

        self.tab_menu_options = {}
        self.tab_menu_options['main'] = self.tab_widget

        # Create layout for main window/dialog, and add the tab widget to it
        window_layout = QVBoxLayout()
        window_layout.addWidget(self.tab_widget)

        # Set the layout for the main window/dialog
        self.setLayout(window_layout)

        # dirs
        self.root_dir = root_dir
        self.user_files_dir = user_files_dir

    def add_tab(self, new_tab: FrequencyManTab) -> None:

        self.tab_menu_options[new_tab.id] = new_tab

        tab_layout = QVBoxLayout()
        new_tab.setLayout(tab_layout)

        self.tab_widget.addTab(new_tab, new_tab.name)

        new_tab.on_tab_created(tab_layout)

    @override
    def closeEvent(self, a0: Union[QCloseEvent, None]) -> None:

        if a0 is None:
            return

        for tab in self.tab_widget.findChildren(FrequencyManTab):
            result = tab.on_window_closing()
            if result is not None and result == 1:
                a0.ignore()
                return

        a0.accept()
