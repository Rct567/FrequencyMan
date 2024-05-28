"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from typing import Any, Optional, Tuple, Callable

from aqt import QAction
from aqt.qt import *
from aqt.main import AnkiQt

try:
    from ..version import FREQUENCYMAN_VERSION
    fm_version = FREQUENCYMAN_VERSION
except ImportError:
    fm_version = ""


class FrequencyManTab(QWidget):

    id: str
    name: str
    first_paint_done: bool

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.first_paint_done = False

    def on_tab_created(self, tab_layout: QVBoxLayout):
        pass

    def on_tab_painted(self, tab_layout: QLayout):
        pass

    def on_window_closing(self) -> Optional[int]:
        pass

    def paintEvent(self, a0: Optional[QPaintEvent]):
        if not self.first_paint_done and (layout := self.layout()) is not None:
            self.first_paint_done = True
            self.on_tab_painted(layout)


# FrequencyMan Main Window class

class FrequencyManMainWindow(QDialog):

    root_dir: str
    user_files_dir: str

    mw: AnkiQt
    is_dark_mode: bool

    tab_menu_options: dict[str, QWidget]

    addon_config: dict[str, Any]
    addon_config_write: Callable[[dict[str, Any]], None]

    def __init__(self, mw: AnkiQt, root_dir: str, user_files_dir: str):

        super().__init__(mw)
        self.mw = mw
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

        # Addon config
        self.addon_config = {}
        addon_config = mw.addonManager.getConfig(__name__)
        if isinstance(addon_config, dict):
            self.addon_config = addon_config

        self.addon_config_write = lambda config: mw.addonManager.writeConfig(__name__, config)

        # dirs
        self.root_dir = root_dir
        self.user_files_dir = user_files_dir

    def add_tab(self, new_tab: FrequencyManTab) -> None:

        self.tab_menu_options[new_tab.id] = new_tab

        tab_layout = QVBoxLayout()
        new_tab.setLayout(tab_layout)

        self.tab_widget.addTab(new_tab, new_tab.name)

        new_tab.on_tab_created(tab_layout)

    def closeEvent(self, a0: Union[QCloseEvent, None]) -> None:

        if a0 is None:
            return

        for tab in self.tab_widget.findChildren(FrequencyManTab):
            result = tab.on_window_closing()
            if result is not None and result == 1:
                a0.ignore()
                return

        a0.accept()


