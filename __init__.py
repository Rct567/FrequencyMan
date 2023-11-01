from typing import Sequence, Tuple

from aqt import QAction
from aqt.qt import *
from aqt.main import AnkiQt

import anki.cards
from anki.collection import Collection
from aqt.utils import showInfo

from .frequencyman.card_ranker import CardRanker
from .frequencyman.lib.utilities import *
from .frequencyman.target_corpus_data import TargetCorpusData
from .frequencyman.word_frequency_list import WordFrequencyLists
from .frequencyman.target_list import Target, TargetList


def get_mw():
    from aqt import mw # type: ignore
    return mw

mw:AnkiQt = get_mw()

# FrequencyMan Main Window class
class FrequencyManMainWindow(QDialog):
    
    target_data:TargetList
    
    def __init__(self, mw:AnkiQt):
        super().__init__(mw) 
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
        self.addon_config = mw.addonManager.getConfig(__name__)
        
    def create_new_tab(self, tab_id: str, tab_name: str) -> Tuple[QVBoxLayout, QWidget]:
        tab = QWidget()
        self.tab_menu_options[tab_id] = tab
        
        # layout for the new tab
        tab_layout = QVBoxLayout()
        tab.setLayout(tab_layout)

        # Add new tab to the main tab widget
        self.tab_widget.addTab(tab, tab_name)
         
        return (tab_layout, tab)

 
def reorder_target_cards(target:Target, word_frequency_lists:WordFrequencyLists, col:Collection) -> bool:
    
    target_search_query = target.construct_search_query()
    if "note:" not in target_search_query:
        showInfo("No valid note type defined. At least one note is required for reordering!")
        return False
    
    # load frequency lists for target  
    word_frequency_lists.load_frequency_lists(target.get_notes_language_keys())
    
    # Get results for target
    
    target_all_cards_ids:Sequence[int] = col.find_cards(target_search_query, order="c.due asc")
    target_all_cards:list[anki.cards.Card] = [col.get_card(card_id) for card_id in target_all_cards_ids]
    
    target_new_cards = [card for card in target_all_cards if card.queue == 0]
    target_new_cards_ids = [card.id for card in target_new_cards]

    showInfo("Reordering {} new cards in a collection of {} cards!".format(len(target_new_cards_ids), len(target_all_cards))) 
    
    cards_corpus_data = TargetCorpusData()
    cards_corpus_data.create_data(target_all_cards, target, col)
    
    # Sort cards
    card_ranker = CardRanker(cards_corpus_data, word_frequency_lists, col)
    card_rankings = card_ranker.calc_cards_ranking(target_new_cards)
    sorted_cards = sorted(target_new_cards, key=lambda card: card_rankings[card.id], reverse=True)
    sorted_card_ids = [card.id for card in sorted_cards]

    # Avoid making unnecessary changes
    if target_new_cards_ids == sorted_card_ids:
        showInfo("No card needed sorting!")
        return False
    
    # Reposition cards and apply changes
    col.sched.forgetCards(sorted_card_ids)
    col.sched.reposition_new_cards(
        card_ids=sorted_card_ids,
        starting_from=0, step_size=1,
        randomize=False, shift_existing=True
    )
    
    showInfo("Done with sorting!")
    
    return True
  
  
def execute_reorder(fm_window:FrequencyManMainWindow, target_list:TargetList):
    
    frequency_lists_dir = os.path.join(os.path.dirname(__file__), 'user_files', 'frequency_lists')
    word_frequency_list = WordFrequencyLists(frequency_lists_dir)
        
    col = mw.col
    
    if not isinstance(col, Collection):
        return
    
    for target in target_list:
        reorder_target_cards(target, word_frequency_list, col)
    

def create_tab_sort_cards(fm_window:FrequencyManMainWindow):
    # Create a new tab and its layout
    (tab_layout, tab) = fm_window.create_new_tab('sort_cards', "Sort cards")
    
    # target data
    target_list = TargetList()
    if fm_window.addon_config and "fm_reorder_target" in fm_window.addon_config:
        target_list.set_targets(fm_window.addon_config.get("fm_reorder_target", []))

    # Textarea widget
    target_data_textarea = QTextEdit()
    target_data_textarea.setMinimumHeight(300);
    target_data_textarea.setAcceptRichText(False)
    target_data_textarea.setStyleSheet("font-weight: bolder; font-size: 14px; line-height: 1.2;") 
    target_data_textarea.setText(target_list.dump_json())
    
    # Check if the JSON and target data is valid
    def check_textarea_json_validity():
        (validity_state, targets_defined) = TargetList.handle_json(target_data_textarea.toPlainText());
        palette = QPalette()
        if (validity_state == 1):
            palette.setColor(QPalette.ColorRole.Text, QColor("#23b442")) # Green
            target_list.set_targets(targets_defined)
        if (validity_state == -1):
            palette.setColor(QPalette.ColorRole.Text, QColor("#bb462c")) # Red
        target_data_textarea.setPalette(palette)   

    # Connect the check_json_validity function to textChanged signal
    target_data_textarea.textChanged.connect(check_textarea_json_validity)
    check_textarea_json_validity()

    # Create the "Reorder Cards" button
    exec_reorder_button = QPushButton("Reorder Cards")
    exec_reorder_button.setStyleSheet("font-size: 16px; font-weight: bold; background-color: #23b442; color: white; border:2px solid #23a03e")
    exec_reorder_button.clicked.connect(lambda: execute_reorder(fm_window, target_list))
    
    tab_layout.addWidget(target_data_textarea)
    tab_layout.addWidget(exec_reorder_button)
    tab_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)) # Add an empty spacer row to compress the rows above
    

def create_tab_word_overview(fm_window:FrequencyManMainWindow):
    (tab_layout, tab) = fm_window.create_new_tab('word_overview', "Word overview")
    # Create a label to display "Test" in the panel
    label = QLabel("** Overview of easy and hard words....")
    tab_layout.addWidget(label)

     
# Open the 'FrequencyMan main window'
def open_frequencyman_main_window(mw:AnkiQt):
    fm_window = FrequencyManMainWindow(mw)
    create_tab_sort_cards(fm_window);
    create_tab_word_overview(fm_window);
    fm_window.exec()


# Add "FrequencyMan" menu option in the "Tools" menu of the main Anki window

def add_frequencyman_menu_option_to_anki_tools_menu(mw:AnkiQt):
    action = QAction("FrequencyMan", mw)
    action.triggered.connect(lambda: open_frequencyman_main_window(mw))
    mw.form.menuTools.addAction(action)

if isinstance(mw, AnkiQt):
    add_frequencyman_menu_option_to_anki_tools_menu(mw)


