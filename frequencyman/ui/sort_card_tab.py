import json
from typing import Tuple
from anki.collection import Collection
from aqt.utils import askUser, showWarning

from aqt import QAction
from aqt.qt import *
from aqt.main import AnkiQt
from aqt.utils import showInfo, askUser, showWarning

from .main_window import FrequencyManMainWindow

from ..lib.utilities import var_dump_log
from ..lib.event_logger import EventLogger

from ..target import ConfigTargetDataNotes
from ..card_ranker import CardRanker
from ..target_corpus_data import TargetCorpusData
from ..word_frequency_list import WordFrequencyLists
from ..target_list import ConfigTargetData, Target, TargetList

def reorder_target_cards(target:Target, word_frequency_lists:WordFrequencyLists, col:Collection, event_logger:EventLogger) -> Tuple[bool, str]:
    
    if "note:" not in target.get_search_query():
        warning_msg = "No valid note type defined. At least one note is required for reordering!"
        event_logger.addEntry(warning_msg)
        return (False, warning_msg)
    
    # Check defined target lang keys and then load frequency lists for target  
    for lang_key in target.get_notes_language_keys():
        if not word_frequency_lists.key_has_frequency_list_file(lang_key):
            warning_msg = "No word frequency list file found for key '{}'!".format(lang_key)
            event_logger.addEntry(warning_msg)
            return (False, warning_msg)
    
    with event_logger.addBenchmarkedEntry("Loading word frequency lists."):
        word_frequency_lists.load_frequency_lists(target.get_notes_language_keys())
    
    # Get cards for target
    with event_logger.addBenchmarkedEntry("Getting target cards from collection."):
        target_result = target.get_cards(col)
        
    event_logger.addEntry("Found {:n} new cards in a target collection of {:n} cards.".format(len(target_result.new_cards_ids), len(target_result.all_cards)))
    
    # Get corpus data
    cards_corpus_data = TargetCorpusData()
    with event_logger.addBenchmarkedEntry("Creating corpus data from target cards."):
        cards_corpus_data.create_data(target_result.all_cards, target, col)
    
    # Sort cards
    with event_logger.addBenchmarkedEntry("Ranking cards and creating a new sorted list."):
        card_ranker = CardRanker(cards_corpus_data, word_frequency_lists, col)
        card_rankings = card_ranker.calc_cards_ranking(target_result.new_cards)
        sorted_cards = sorted(target_result.new_cards, key=lambda card: card_rankings[card.id], reverse=True)
        sorted_card_ids = [card.id for card in sorted_cards]

    
    if target_result.new_cards_ids == sorted_card_ids: # Avoid making unnecessary changes 
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
    
    
def execute_reorder(col:Collection, target_list:TargetList, word_frequency_lists:WordFrequencyLists):
    
    if not isinstance(col, Collection):
        showInfo("Collection not found!")
        return
    
    if not target_list.has_targets():
        showInfo("No targets defined!")
        return
    
    event_logger = EventLogger()

    for target in target_list:
        with event_logger.addBenchmarkedEntry(f"Reordering target #{target.index_num}."):
            (sorted, warning_msg) = reorder_target_cards(target, word_frequency_lists, col, event_logger)
            if (warning_msg != ""): 
                showWarning(warning_msg)
            
            
    target_word = "targets" if len(target_list) > 1 else "target"
    event_logger.addEntry("Done with sorting {} {}!".format(len(target_list), target_word), showInfo)
            
    var_dump_log(event_logger.events)


class SortCardsTab:
    
    @staticmethod
    def create_new_tab(fm_window:FrequencyManMainWindow, col:Collection):
        # Create a new tab and its layout
        (tab_layout, tab) = fm_window.create_new_tab('sort_cards', "Sort cards")
        
        #
        frequency_lists_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'user_files', 'frequency_lists')
        word_frequency_lists = WordFrequencyLists(frequency_lists_dir)
        
        # target data
        target_list = TargetList(word_frequency_lists)
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
            
        # Validation line below textarea, with line of text and buttons on the right
        def create_validation_line_widget() -> Tuple[QWidget,QLabel]:

            layout = QHBoxLayout()
            layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            # Create a QLabel for the left side
            validation_txt_info = QLabel("Hello :)")
            validation_txt_info.setStyleSheet("font-weight: bolder; font-size: 13px;")
            validation_txt_info.setVisible(False)
            layout.addWidget(validation_txt_info)

            # Create two QPushButton widgets for the right side
            button1 = QPushButton("Reset")
            button2 = QPushButton("Save")
            layout.addStretch(1)
            layout.addWidget(button1)
            layout.addWidget(button2)

            # Set the layout for the QWidget
            line_widget = QWidget()
            line_widget.setStyleSheet("margin-top:0px;")
            line_widget.setLayout(layout)

            return (line_widget, validation_txt_info)
        
        (target_data_validation_line, target_data_validation_info_txt) = create_validation_line_widget()      
        
        # Ask to save to config if new targets have been defined
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
            (json_validity_state, targets_defined, err_desc) = target_list.handle_json(target_data_textarea.toPlainText());
            palette = QPalette()
            if (json_validity_state == 1): # valid
                palette.setColor(QPalette.ColorRole.Text, QColor("#23b442")) # Green
                target_data_validation_info_txt.setVisible(False)
                target_list.set_targets(targets_defined) # set new targets
            else:
                target_data_validation_info_txt.setVisible(True)
            if (json_validity_state == -1): # invalid json
                palette.setColor(QPalette.ColorRole.Text, QColor("#bb462c")) # Red
            target_data_textarea.setPalette(palette) 
            target_data_validation_info_txt.setText(err_desc)  
            return (json_validity_state, targets_defined, err_desc)

        # Connect the check_json_validity function to textChanged signal
        target_data_textarea.textChanged.connect(check_textarea_json_validity)
        check_textarea_json_validity()

        # Create the "Reorder Cards" button
        def user_clicked_reorder_button():
            (json_validity_state, targets_defined, err_desc) = check_textarea_json_validity()
            if json_validity_state == 1:
                save_config_new_targets(targets_defined)
                execute_reorder(col, target_list, word_frequency_lists)
            elif target_list.has_targets() and askUser("Defined targets are not valid.\n\n"+err_desc+"\n\nRestore previously defined targets?"):
                target_data_textarea.setText(target_list.dump_json())
            else:
                showWarning("Defined targets are not valid!\n\n"+err_desc)     
        
        exec_reorder_button = QPushButton("Reorder Cards")
        exec_reorder_button.setStyleSheet("font-size: 16px; font-weight: bold; background-color: #23b442; color: white; border:2px solid #23a03e; margin-top:20px;")
        exec_reorder_button.clicked.connect(user_clicked_reorder_button)  
        
        tab_layout.setSpacing(0)
        tab_layout.addWidget(target_data_textarea)
        tab_layout.addWidget(target_data_validation_line)
        tab_layout.addWidget(exec_reorder_button)
        tab_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)) # Add an empty spacer row to compress the rows above
 