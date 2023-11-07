import json
from typing import Sequence, Tuple

from aqt import QAction
from aqt.qt import *
from aqt.main import AnkiQt

from anki.cards import CardId, Card
from anki.collection import Collection
from aqt.utils import showInfo, askUser, tooltip, showWarning

from .frequencyman.lib.event_logger import EventLogger
from .frequencyman.card_ranker import CardRanker
from .frequencyman.lib.utilities import *
from .frequencyman.target_corpus_data import TargetCorpusData
from .frequencyman.word_frequency_list import WordFrequencyLists
from .frequencyman.target_list import ConfigTargetData, ConfigTargetDataNotes, Target, TargetList


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
        self.addon_config_write: Callable[[dict[str, Any]], None] = lambda config: mw.addonManager.writeConfig(__name__, config)
        
    def create_new_tab(self, tab_id: str, tab_name: str) -> Tuple[QVBoxLayout, QWidget]:
        tab = QWidget()
        self.tab_menu_options[tab_id] = tab
        
        # layout for the new tab
        tab_layout = QVBoxLayout()
        tab.setLayout(tab_layout)

        # Add new tab to the main tab widget
        self.tab_widget.addTab(tab, tab_name)
         
        return (tab_layout, tab)

 
def reorder_target_cards(target:Target, word_frequency_lists:WordFrequencyLists, col:Collection, event_logger:EventLogger) -> Tuple[bool, str]:
    
    target_search_query = target.construct_search_query()

    if "note:" not in target_search_query:
        warning_msg = "No valid note type defined. At least one note is required for reordering!"
        event_logger.addEntry(warning_msg)
        return (False, warning_msg)
    
    # Load frequency lists for target  
    for lang_key in target.get_notes_language_keys():
        if not word_frequency_lists.key_has_list_file(lang_key):
            warning_msg = "No word frequency list file found for key '{}'!".format(lang_key)
            event_logger.addEntry(warning_msg)
            return (False, warning_msg)
    
    with event_logger.addBenchmarkedEntry("Loading word frequency lists."):
        word_frequency_lists.load_frequency_lists(target.get_notes_language_keys())
    
    # Get cards for target
    with event_logger.addBenchmarkedEntry("Getting target cards from collection."):
        target_all_cards_ids = col.find_cards(target_search_query, order="c.due asc")
        target_all_cards = [col.get_card(card_id) for card_id in target_all_cards_ids]
        
        target_new_cards = [card for card in target_all_cards if card.queue == 0]
        target_new_cards_ids = [card.id for card in target_new_cards]
        
    event_logger.addEntry("Found {:n} new cards in a target collection of {:n} cards.".format(len(target_new_cards_ids), len(target_all_cards)))
      
    # Get corpus data
    cards_corpus_data = TargetCorpusData()
    with event_logger.addBenchmarkedEntry("Creating corpus data from target cards."):
        cards_corpus_data.create_data(target_all_cards, target, col)
    
    # Sort cards
    with event_logger.addBenchmarkedEntry("Ranking cards and creating a new sorted list."):
        card_ranker = CardRanker(cards_corpus_data, word_frequency_lists, col)
        card_rankings = card_ranker.calc_cards_ranking(target_new_cards)
        sorted_cards = sorted(target_new_cards, key=lambda card: card_rankings[card.id], reverse=True)
        sorted_card_ids = [card.id for card in sorted_cards]

    
    if target_new_cards_ids == sorted_card_ids: # Avoid making unnecessary changes 
        event_logger.addEntry("Cards order was already up-to-date!")
    else:
        # Reposition cards and apply changes
        with event_logger.addBenchmarkedEntry("Reposition cards in collection."):
            col.sched.forgetCards(sorted_card_ids)
            col.sched.reposition_new_cards(
                card_ids=sorted_card_ids,
                starting_from=0, step_size=1,
                randomize=False, shift_existing=True
            )
    
    event_logger.addEntry(f"Done with sorting target #{target.index_num}!")
    
    return (True, "")
  
  
def execute_reorder(col:Collection, target_list:TargetList):
    
    if not isinstance(col, Collection):
        showInfo("Collection not found!")
        return
    
    if not target_list.has_targets():
        showInfo("No targets defined!")
        return
    
    event_logger = EventLogger()
    
    frequency_lists_dir = os.path.join(os.path.dirname(__file__), 'user_files', 'frequency_lists')
    word_frequency_lists = WordFrequencyLists(frequency_lists_dir)
    
    for target in target_list:
        with event_logger.addBenchmarkedEntry(f"Reordering target #{target.index_num}."):
            (sorted, warning_msg) = reorder_target_cards(target, word_frequency_lists, col, event_logger)
            if (warning_msg != ""): 
                showWarning(warning_msg)
            
             
    target_word = "targets" if len(target_list) > 1 else "target"
    event_logger.addEntry("Done with sorting {} {}!".format(len(target_list), target_word), showInfo)
            
    var_dump_log(event_logger.events)
    

def create_tab_sort_cards(fm_window:FrequencyManMainWindow, col:Collection):
    # Create a new tab and its layout
    (tab_layout, tab) = fm_window.create_new_tab('sort_cards', "Sort cards")
    
    # target data
    target_list = TargetList()
    if fm_window.addon_config and "fm_reorder_target_list" in fm_window.addon_config:
        target_list.set_targets(fm_window.addon_config.get("fm_reorder_target_list", []))

    # Textarea widget
    target_data_textarea = QTextEdit()
    target_data_textarea.setMinimumHeight(300);
    target_data_textarea.setAcceptRichText(False)
    target_data_textarea.setStyleSheet("font-weight: bolder; font-size: 14px; line-height: 1.2;") 
    if (target_list.has_targets()):
        target_data_textarea.setText(target_list.dump_json())
    else: # when does this even happen?
        example_data_notes_item:ConfigTargetDataNotes = {'name': '** name of notes type **', 'fields': {"Front": "JP", "Back": "EN"}}
        example_target:ConfigTargetData = {'deck': '** name of main deck **', 'notes': [example_data_notes_item]}
        example_target_list = [example_target]
        target_data_textarea.setText(json.dumps(example_target_list, indent=4))
        
    # Validation info
    validation_info = QLabel()
    validation_info.setText("Hello :)")
    validation_info.setStyleSheet("font-weight: bolder; font-size: 13px; line-height: 1.2; margin-bottom:20px;")
    validation_info.setVisible(False)
    
    def save_config_new_targets(targets_defined: list[ConfigTargetData]):
        if fm_window.addon_config is None or "fm_reorder_target_list" not in fm_window.addon_config:
            return
        if fm_window.addon_config['fm_reorder_target_list'] == targets_defined:
            return
        if askUser("Defined targets have changed. Save them to config?"):
            new_config = fm_window.addon_config
            new_config['fm_reorder_target_list'] = targets_defined
            fm_window.addon_config_write(new_config)     
    
    # Check if the JSON and target data is valid
    def check_textarea_json_validity() -> Tuple[int, list[ConfigTargetData], str]:
        (json_validity_state, targets_defined, err_desc) = TargetList.handle_json(target_data_textarea.toPlainText());
        palette = QPalette()
        if (json_validity_state == 1): # valid
            palette.setColor(QPalette.ColorRole.Text, QColor("#23b442")) # Green
            validation_info.setVisible(False)
            target_list.set_targets(targets_defined) # set new targets
        else:
            validation_info.setVisible(True)
        if (json_validity_state == -1): # invalid json
            palette.setColor(QPalette.ColorRole.Text, QColor("#bb462c")) # Red
        target_data_textarea.setPalette(palette) 
        validation_info.setText(err_desc)  
        return (json_validity_state, targets_defined, err_desc)

    # Connect the check_json_validity function to textChanged signal
    target_data_textarea.textChanged.connect(check_textarea_json_validity)
    check_textarea_json_validity()

    # Create the "Reorder Cards" button
    def user_clicked_reorder_button():
        (json_validity_state, targets_defined, err_desc) = check_textarea_json_validity()
        if json_validity_state == 1:
            save_config_new_targets(targets_defined)
            execute_reorder(col, target_list)
        elif target_list.has_targets() and askUser("Defined targets are not valid.\n\n"+err_desc+"\n\nRestore previous defined targets?"):
            target_data_textarea.setText(target_list.dump_json())
        else:
            showWarning("Defined targets are not valid!\n\n"+err_desc)     
    
    exec_reorder_button = QPushButton("Reorder Cards")
    exec_reorder_button.setStyleSheet("font-size: 16px; font-weight: bold; background-color: #23b442; color: white; border:2px solid #23a03e")
    exec_reorder_button.clicked.connect(user_clicked_reorder_button)
    
    tab_layout.addWidget(target_data_textarea)
    tab_layout.addWidget(validation_info)
    tab_layout.addWidget(exec_reorder_button)
    tab_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)) # Add an empty spacer row to compress the rows above
    

def create_tab_word_overview(fm_window:FrequencyManMainWindow):
    (tab_layout, tab) = fm_window.create_new_tab('word_overview', "Word overview")
    # Create a label to display "Test" in the panel
    label = QLabel("Overview of: 1. familiar words not in word frequency lists, 2 words with most lexical_discrepancy")
    tab_layout.addWidget(label)

     
# Open the 'FrequencyMan main window'
def open_frequencyman_main_window(mw:AnkiQt):
    
    if not isinstance(mw.col, Collection):
        return
    
    fm_window = FrequencyManMainWindow(mw)
    create_tab_sort_cards(fm_window, mw.col);
    create_tab_word_overview(fm_window);
    fm_window.exec()


# Add "FrequencyMan" menu option in the "Tools" menu of the main Anki window

def add_frequencyman_menu_option_to_anki_tools_menu(mw:AnkiQt):
    action = QAction("FrequencyMan", mw)
    action.triggered.connect(lambda: open_frequencyman_main_window(mw))
    mw.form.menuTools.addAction(action)

if isinstance(mw, AnkiQt):
    add_frequencyman_menu_option_to_anki_tools_menu(mw)


