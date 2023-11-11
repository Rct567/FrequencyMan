import json
from typing import Tuple
from anki.collection import Collection

from aqt import QAction
from aqt.qt import *
from aqt.main import AnkiQt
from aqt.utils import showInfo, askUser, showWarning

from .main_window import FrequencyManMainWindow

from ..card_ranker import CardRanker
from ..target_corpus_data import TargetCorpusData
from ..word_frequency_list import WordFrequencyLists
from ..target_list import ConfigTargetData, Target, TargetList

from ..lib.utilities import var_dump_log
from ..lib.event_logger import EventLogger


class OverviewTab:

    fm_window: FrequencyManMainWindow

    def __init__(self, fm_window: FrequencyManMainWindow) -> None:
        self.fm_window = fm_window

    def create_new_tab(self, ):

        (tab_layout, tab) = self.fm_window.create_new_tab('word_overview', "Word overview")

        label = QLabel("Overview of:\n\n1. familiar words not in word frequency lists.\n2. words with most lexical_discrepancy.")
        tab_layout.addWidget(label)

        tab_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))  # Add an empty spacer row to compress the rows above
