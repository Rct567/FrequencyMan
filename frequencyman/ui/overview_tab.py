"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

import json
from typing import Tuple
from anki.collection import Collection

from aqt import QAction
from aqt.qt import *
from aqt.main import AnkiQt
from aqt.utils import showInfo, askUser, showWarning

from .main_window import FrequencyManMainWindow, FrequencyManTab

from ..card_ranker import CardRanker
from ..target_corpus_data import TargetCorpusData
from ..language_data import LanguageData
from ..target_list import ConfiguredTarget, Target, TargetList

from ..lib.utilities import var_dump_log
from ..lib.event_logger import EventLogger


class OverviewTab(FrequencyManTab):

    fm_window: FrequencyManMainWindow

    def __init__(self, fm_window: FrequencyManMainWindow) -> None:
        super().__init__()
        self.id = 'word_overview'
        self.name = 'Word overview'
        self.fm_window = fm_window

    def on_tab_created(self, tab_layout: QVBoxLayout):

        label = QLabel("Overview of:\n\n1. familiar words not in word frequency lists.\n2. words with most lexical_discrepancy.")
        tab_layout.addWidget(label)

        tab_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))  # Add an empty spacer row to compress the rows above

