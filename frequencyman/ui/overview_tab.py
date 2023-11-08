import json
from typing import Tuple
from anki.collection import Collection
from aqt.utils import askUser, showWarning

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
    
    @staticmethod
    def create_new_tab(fm_window:FrequencyManMainWindow):
        (tab_layout, tab) = fm_window.create_new_tab('word_overview', "Word overview")
        # Create a label to display "Test" in the panel
        label = QLabel("Overview of: 1. familiar words not in word frequency lists, 2 words with most lexical_discrepancy")
        tab_layout.addWidget(label)