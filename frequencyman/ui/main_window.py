"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from __future__ import annotations

from functools import cached_property
from typing import Optional, Union, TYPE_CHECKING

from ..language_data import LanguageData
from ..target_list import TargetList

from ..lib.persistent_cacher import PersistentCacher, NullPersistentCacher, SqlDbFile
from ..lib.utilities import override

from aqt.qt import QMainWindow, QWidget, QVBoxLayout, QLayout, QPaintEvent, QCloseEvent, QTabWidget, QHideEvent

from aqt import dialogs
from aqt.utils import restoreGeom, saveGeom

if TYPE_CHECKING:
    from aqt.main import AnkiQt
    from ..lib.addon_config import AddonConfig
    from anki.collection import Collection
    from pathlib import Path

try:
    from ..version import FREQUENCYMAN_VERSION
    fm_version = FREQUENCYMAN_VERSION
except ImportError:
    fm_version = ""


class FrequencyManTab(QWidget):

    id: str
    name: str
    first_paint_event_done: bool
    focus_event_done: bool
    col: Collection
    fm_window: FrequencyManMainWindow
    fm_config: AddonConfig

    def __init__(self, parent: FrequencyManMainWindow, fm_config: AddonConfig, col: Collection):
        super().__init__(parent)
        self.first_paint_event_done = False
        self.focus_event_done = False
        self.col = col
        self.fm_window = parent
        self.fm_config = fm_config

    def on_tab_created(self, tab_layout: QVBoxLayout):
        pass

    def on_tab_first_paint(self, tab_layout: QLayout):
        pass

    def on_window_closing(self) -> Optional[int]:
        pass

    def on_tab_focus(self, tab_layout: QLayout) -> None:
        pass

    @staticmethod
    def clear_layout(layout: QLayout) -> None:
        while layout.count():
            child = layout.takeAt(0)
            if not child:
                return
            widget = child.widget()
            if not widget:
                return
            widget.deleteLater()

    @cached_property
    def language_data(self) -> LanguageData:

        lang_data_dir = self.fm_window.user_files_dir / 'lang_data'
        if not lang_data_dir.is_dir():
            lang_data_dir.mkdir(parents=True)

        return LanguageData(lang_data_dir)

    @cached_property
    def cacher(self) -> PersistentCacher:

        if self.fm_config.is_enabled('use_persistent_cache', default=True):
            return PersistentCacher(SqlDbFile(self.fm_window.user_files_dir / 'cacher_data.sqlite'))
        else:
            return NullPersistentCacher()

    def init_new_target_list(self) -> TargetList:

        return TargetList(self.language_data, self.cacher, self.col)

    @override
    def paintEvent(self, a0: Optional[QPaintEvent]):
        if (layout := self.layout()) is None:
            return
        if not self.first_paint_event_done:
            self.first_paint_event_done = True
            self.on_tab_first_paint(layout)
        if not self.focus_event_done:
            self.focus_event_done = True
            self.on_tab_focus(layout)

    @override
    def hideEvent(self, a0: Optional[QHideEvent]):
        self.focus_event_done = False
        super().hideEvent(a0)


# FrequencyMan Main Window class

class FrequencyManMainWindow(QMainWindow):

    key = "FrequencyMan"

    root_dir: Path
    user_files_dir: Path

    mw: AnkiQt
    col: Collection
    fm_config: AddonConfig
    is_dark_mode: bool

    tab_menu_options: dict[str, QWidget]

    def __init__(self, mw: AnkiQt, col: Collection, fm_config: AddonConfig, root_dir: Path, user_files_dir: Path):

        super().__init__(mw)
        self.mw = mw
        self.col = col
        self.fm_config = fm_config
        self.is_dark_mode = mw.app.styleSheet().lower().find("dark") != -1

        if fm_version != "":
            self.setWindowTitle("FrequencyMan v"+fm_version)
        else:
            self.setWindowTitle("FrequencyMan")

        self.setMinimumSize(650, 550)
        restoreGeom(self, FrequencyManMainWindow.key)

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        window_layout = QVBoxLayout()
        central_widget.setLayout(window_layout)

        # Create a tab widget
        self.tab_widget = QTabWidget()
        self.tab_menu_options = {}
        self.tab_menu_options['main'] = self.tab_widget
        window_layout.addWidget(self.tab_widget)

        # dirs
        self.root_dir = root_dir
        self.user_files_dir = user_files_dir

    def add_tab(self, new_tab: FrequencyManTab) -> None:

        self.tab_menu_options[new_tab.id] = new_tab

        tab_layout = QVBoxLayout()
        new_tab.setLayout(tab_layout)

        self.tab_widget.addTab(new_tab, new_tab.name)

        new_tab.on_tab_created(tab_layout)

    def show_tab(self, tab_id: str) -> QWidget:
        self.tab_widget.setCurrentWidget(self.tab_menu_options[tab_id])
        return self.tab_menu_options[tab_id]

    @override
    def closeEvent(self, a0: Union[QCloseEvent, None]) -> None:

        if a0 is None:
            return

        for tab in self.tab_widget.findChildren(FrequencyManTab):
            result = tab.on_window_closing()
            if result is not None and result == 1:
                a0.ignore()
                return

        saveGeom(self, self.key)

        # Mark dialog as closed
        try:
            if hasattr(dialogs, "markClosed"):
                dialogs.markClosed(FrequencyManMainWindow.key)
        except Exception:
            # In non‑Anki or test environments, dialogs may not be fully initialized
            pass

        a0.accept()
