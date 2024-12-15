"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from anki.collection import Collection

from aqt.qt import QVBoxLayout, QLabel, QSpacerItem, QSizePolicy
from aqt.main import AnkiQt
from aqt.utils import showInfo, askUser, showWarning

from .main_window import FrequencyManMainWindow, FrequencyManTab

from ..lib.utilities import var_dump_log, override


class OverviewTab(FrequencyManTab):

    def __init__(self, fm_window: FrequencyManMainWindow, col: Collection) -> None:
        super().__init__(fm_window, col)
        self.id = 'word_overview'
        self.name = 'Word overview'

    @override
    def on_tab_created(self, tab_layout: QVBoxLayout) -> None:

        label = QLabel("Overview of:\n\n1. familiar words not in word frequency lists.\n2. words with most lexical_discrepancy.")
        tab_layout.addWidget(label)

        tab_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))  # Add an empty spacer row to compress the rows above

