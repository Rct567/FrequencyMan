import json
import random
from aqt import QAction# type: ignore
from aqt.qt import *
import anki.cards
from anki.models import NoteType
from anki.cards import Card
from aqt.utils import showInfo
from typing import Dict, List, Optional, Tuple, TypedDict

from .frequencyman.word_frequency_list import WordFrequencyLists
from .frequencyman.text_processing import TextProcessing
from .frequencyman.target_list import Target, TargetList
import pprint

def get_mw():
    from aqt import mw # type: ignore
    return mw

mw = get_mw()

def var_dump(var) -> None:
    showInfo(pprint.pformat(var))

# FrequencyMan Main Window class
class FrequencyManMainWindow(QDialog):
    
    target_data:TargetList
    
    def __init__(self):
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
        
        # Target data (list of targets to reorder)
        self.target_data = TargetList()
        if "fm_reorder_target" in self.addon_config:
            self.target_data.load(self.addon_config.get("fm_reorder_target"))
        
        
    def create_new_tab(self, tab_id: str, tab_name: str) -> Tuple[QVBoxLayout, QWidget]:
        tab = QWidget()
        self.tab_menu_options[tab_id] = tab
        
        # layout for the new tab
        tab_layout = QVBoxLayout()
        tab.setLayout(tab_layout)

        # Add new tab to the main tab widget
        self.tab_widget.addTab(tab, tab_name)
         
        return (tab_layout, tab)
  
    
def get_target_cards_corpus_data(target_cards:list[anki.cards.Card], target:Target) -> dict[str, dict]:

    target_fields_by_notes_name = target.getNotes()
    handled_cards = {}
    
    for card in target_cards:
        card_note = mw.col.getNote(card.nid)
        card_note_name = card_note.model()['name']
         
        if card_note_name in target_fields_by_notes_name: # note type  name is defined as target
            target_note_fields = target_fields_by_notes_name[card_note_name]
            card_note_items_accepted = []
            for key, val in card_note.items():
                if key in target_note_fields.keys():
                    card_note_items_accepted.append({
                        "field_name": key, 
                        "field_value_plain_text": TextProcessing.get_plain_text(val), 
                        "field_value_tokenized": TextProcessing.get_word_tokens_from_text(val), 
                        "target_language_id": target_note_fields[key]
                    })
            handled_cards[card.id] = {'card': card, "accepted_fields": card_note_items_accepted}
    return {"handled_cards": handled_cards}

    
def get_card_ranking(card:anki.cards.Card, cards_corpus_data, word_frequency_lists:WordFrequencyLists) -> int:
    return random.randint(1, 256)

 
def reorder_target_cards(target:Target, word_frequency_lists:WordFrequencyLists) -> bool:
    target_search_query = target.construct_search_query()
    if "note:" not in target_search_query:
        showInfo("No valid note type defined. At least one note is required for reordering!")
        return False

    # Get results for target
    target_cards_ids = mw.col.find_cards(target_search_query, order="c.due asc")
    target_cards = [mw.col.get_card(card_id) for card_id in target_cards_ids]
    target_new_cards = [card for card in target_cards if card.queue == 0]
    target_new_cards_ids = [card.id for card in target_new_cards]
    cards_corpus_data = get_target_cards_corpus_data(target_cards, target)
    
    var_dump({'num_cards': len(target_cards), 'num_new_cards': len(target_new_cards), 'query': target_search_query})
    
    # Sorted cards
    sorted_cards = sorted(target_new_cards, key=lambda card: get_card_ranking(card, cards_corpus_data, word_frequency_lists))
    sorted_card_ids = [card.id for card in sorted_cards]

    # Avoid making unnecessary changes
    if target_new_cards_ids == sorted_card_ids:
        showInfo("No card needed sorting!")
        return False
    
    # Reposition cards and apply changes
    mw.col.sched.reposition_new_cards(
        card_ids=sorted_card_ids,
        starting_from=0, step_size=1,
        randomize=False, shift_existing=True
    )
    
    showInfo("Done with sorting!")
    
    return True
    
def execute_reorder(fm_window:FrequencyManMainWindow):
    showInfo("Reordering!") 
    # Word frequency list
    word_frequency_list = WordFrequencyLists('user_files/frequency_lists/')
    for target in fm_window.target_data:
        reorder_target_cards(target, word_frequency_list)
    

def create_tab_sort_cards(fm_window: FrequencyManMainWindow):
    # Create a new tab and its layout
    (tab_layout, tab) = fm_window.create_new_tab('sort_cards', "Sort cards")

    # Textarea widget
    target_data_textarea = QTextEdit()
    target_data_textarea.setMinimumHeight(300);
    target_data_textarea.setAcceptRichText(False)
    target_data_textarea.setStyleSheet("font-weight: bolder; font-size: 14px; line-height: 1.2;") 
    target_data_textarea.setText(fm_window.target_data.dump_json())
    
    # Check if the JSON and target data is valid
    def check_textarea_json_validity():
        (validity_state, target_data) = TargetList.handle_json(target_data_textarea.toPlainText());
        palette = QPalette()
        if (validity_state == 1):
            palette.setColor(QPalette.ColorRole.Text, QColor("#23b442")) # Green
            fm_window.target_data.load(target_data)
        if (validity_state == -1):
            palette.setColor(QPalette.ColorRole.Text, QColor("#bb462c")) # Red
        target_data_textarea.setPalette(palette)   

    # Connect the check_json_validity function to textChanged signal
    target_data_textarea.textChanged.connect(check_textarea_json_validity)
    check_textarea_json_validity()

    # Create the "Reorder Cards" button
    exec_reorder_button = QPushButton("Reorder Cards")
    exec_reorder_button.setStyleSheet("font-size: 16px; font-weight: bold; background-color: #23b442; color: white; border:2px solid #23a03e")
    exec_reorder_button.clicked.connect(lambda: execute_reorder(fm_window))
    
    tab_layout.addWidget(target_data_textarea)
    tab_layout.addWidget(exec_reorder_button)
    tab_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)) # Add an empty spacer row to compress the rows above
    

def create_tab_word_overview(fm_window: FrequencyManMainWindow):
    (tab_layout, tab) = fm_window.create_new_tab('word_overview', "Word overview")
    # Create a label to display "Test" in the panel
    label = QLabel("** Overview of easy and hard words....")
    tab_layout.addWidget(label)

     
# Open the 'FrequencyMan main window'
def open_frequencyman_main_window():
    fm_window = FrequencyManMainWindow()
    create_tab_sort_cards(fm_window);
    create_tab_word_overview(fm_window);
    fm_window.exec()


# Add "FrequencyMan" menu option in the "Tools" menu of the main Anki window
def add_frequencyman_menu_option_to_anki_tools_menu():
    action = QAction("FrequencyMan", mw)
    action.triggered.connect(open_frequencyman_main_window)
    mw.form.menuTools.addAction(action)


# Main components
add_frequencyman_menu_option_to_anki_tools_menu()


