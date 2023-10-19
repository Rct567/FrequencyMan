import json
from aqt import QAction, mw as anki_main_window # type: ignore
from aqt.qt import *
import aqt
from aqt.utils import showInfo
from typing import List, Optional, Tuple
import pprint

def var_dump(var):
    #showInfo(str(var))
    showInfo(pprint.pformat(var))


# FrequencyMan Main Window class
class FrequencyManMainWindow(QDialog):
    def __init__(self):
        super().__init__(anki_main_window) 
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
        
        self.fm_config:dict = anki_main_window.addonManager.getConfig(__name__)
        
    def create_new_tab(self, tab_id: str, tab_name: str) -> Tuple[QVBoxLayout, QWidget]:
        tab = QWidget()
        self.tab_menu_options[tab_id] = tab
        
        # layout for the new tab
        tab_layout = QVBoxLayout()
        tab.setLayout(tab_layout)

        # Add new tab to the main tab widget
        self.tab_widget.addTab(tab, tab_name)
         
        return (tab_layout, tab)
  
def validate_target_data(target_data: list) -> int: 
    if len(target_data) < 1:
        return 0
    for target in target_data:
        if type(target) != dict or len(target.keys()) == 0:
            return 0
        for key in target.keys():
            if key not in ("deck", "notes"):
                return 0
    return 1

def handle_json_target_data(json_data: str) -> Tuple[int, List]:
    try:
        data:list = json.loads(json_data)
        if type(data) == list:
            return (validate_target_data(data), data)
        return (-1, [])
    except json.JSONDecodeError:
        return (-1, [])
    
def get_cards_corpus_data(cards:list):
    pass
    
def get_card_ranking(card, cards_corpus_data) -> int:
    return 1
    
 
def reorder_target_cards(target:dict) -> bool:
     
    target_notes = target.get("notes", []) if type(target.get("notes")) == list else []
    note_queries = ['"note:'+note_type['name']+'"' for note_type in target_notes if type(note_type['name']) == str]
    
    if len(note_queries) < 1:
        showInfo("No valid note type defined to find cards to reorder. At least one note is required for reordering!")
        return False

    search_query = "(" + " OR ".join(note_queries) + ")";
     
    if "deck" in target: 
        if type(target.get("deck")) == str and len(target.get("deck", '')) > 0:
            target_decks = [target.get("deck", '')]
        elif type(target.get("deck")) == list:
            target_decks = [deck_name for deck_name in target.get("deck", []) if type(deck_name) == str and len(deck_name) > 0]
        else:
            target_decks = []
            
        if len(target_decks) > 0:
            deck_queries = ['"deck:' + deck_name + '"' for deck_name in target_decks if len(deck_name) > 0]
            target_decks_query = " OR ".join(deck_queries)
            search_query = "("+target_decks_query+")" + search_query

    cards_ids = anki_main_window.col.find_cards(search_query, order="c.due asc")
    cards = [anki_main_window.col.get_card(card_id) for card_id in cards_ids]
    new_cards = [card for card in cards if card.queue == 0]
    new_cards_ids = [card.id for card in new_cards]
    cards_corpus_data = get_cards_corpus_data(cards)
    
    var_dump({'num_cards': len(cards), 'num_new_cards': len(new_cards), 'query': search_query})
    
    # Sort cards
    sorted_cards = sorted(new_cards, key=lambda card: get_card_ranking(card, cards_corpus_data))
    sorted_card_ids = [card.id for card in sorted_cards]
    

    # Avoid making unnecessary changes
    if new_cards_ids == sorted_card_ids:
        showInfo("No card needed sorting!")
        return False
    
    # Reposition cards and apply changes
    """ return mw.col.sched.reposition_new_cards(
        card_ids=sorted_card_ids,
        starting_from=0, step_size=1,
        randomize=False, shift_existing=True
    ) """
    
    return True
    
def execute_reorder(target_data_json:str):
    showInfo("Reordering!")
    (target_data_validity_state, target_data) = handle_json_target_data(target_data_json);
    if target_data_validity_state == -1:
        showInfo('JSON Format is not valid. Fail to parse JSON.')
    elif target_data_validity_state == 0:
        showInfo('Target data is not valid. Check necessary such as "deck" and "notes" keys are present.')
      
    for target in target_data:
        reorder_target_cards(target)
    

def create_tab_sort_cards(fm_window: FrequencyManMainWindow):
    # Create a new tab and its layout
    (tab_layout, tab) = fm_window.create_new_tab('sort_cards', "Sort cards")

    # Create textarea widget
    target_data_textarea = QTextEdit()
    target_data_textarea.setMinimumHeight(300);
    target_data_textarea.setAcceptRichText(False)
    target_data_textarea.setStyleSheet("font-weight: bolder; font-size: 14px; line-height: 1.2;")
        
    # Set 'reorder target data from plugin config file' as json in textarea
    if fm_window.fm_config and "fm_reorder_target" in fm_window.fm_config:
        target_data_textarea.setText(json.dumps(fm_window.fm_config.get("fm_reorder_target"), indent=4))
    
    # Check if the JSON and target data is valid
    def check_textarea_json_validity():
        (validity_state, _) = handle_json_target_data(target_data_textarea.toPlainText());
        palette = QPalette()
        if (validity_state == 1):
            palette.setColor(QPalette.ColorRole.Text, QColor("#23b442")) # Green
        if (validity_state == -1):
            palette.setColor(QPalette.ColorRole.Text, QColor("#bb462c")) # Red
        target_data_textarea.setPalette(palette)   

    # Connect the check_json_validity function to textChanged signal
    target_data_textarea.textChanged.connect(check_textarea_json_validity)
    check_textarea_json_validity()

    # Create the "Reorder Cards" button
    exec_reorder_button = QPushButton("Reorder Cards")
    exec_reorder_button.setStyleSheet("font-size: 16px; font-weight: bold; background-color: #23b442; color: white; border:2px solid #23a03e")
    exec_reorder_button.clicked.connect(lambda: execute_reorder(target_data_textarea.toPlainText()))
    
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
    action = QAction("FrequencyMan", anki_main_window)
    action.triggered.connect(open_frequencyman_main_window)
    anki_main_window.form.menuTools.addAction(action)


# Main components
add_frequencyman_menu_option_to_anki_tools_menu()


