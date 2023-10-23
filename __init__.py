from itertools import chain
import itertools
from statistics import mean
import statistics
import time
from uu import Error
from aqt import QAction# type: ignore
from aqt.qt import *
import anki.cards
from anki.models import NoteType
from anki.cards import Card
from aqt.utils import showInfo
from typing import Any, Dict, Iterable, NewType, Tuple, TypedDict
from .frequencyman.word_frequency_list import WordFrequencyLists
from .frequencyman.text_processing import TextProcessing
from .frequencyman.target_list import Target, TargetList
import pprint

def get_mw():
    from aqt import mw # type: ignore
    return mw

mw = get_mw()

var_dump_count = 0

def var_dump(var) -> None:
    global var_dump_count
    if var_dump_count < 10:
        var_str = pprint.pformat(var, sort_dicts=False)
        if len(var_str) > 2000:
            var_str = var_str[:2000].rsplit(' ', 1)[0]
        showInfo(var_str)
        var_dump_count += 1
        
def var_dump_log(var) -> None:
    dump_log_file = os.path.join(os.path.dirname(__file__), 'dump.log')
    with open(dump_log_file, 'a', encoding='utf-8') as file:
            file.write(pprint.pformat(var, sort_dicts=False) + "\n\n=================================================================\n\n")
    var_dump(var)

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
  



NotesWordsFamiliarity = NewType("NotesWordsFamiliarity", Dict[str, dict[str, float]])

class TargetCorpusData(TypedDict): 
    handled_target_cards: dict[int, dict[str, Any]]
    notes_known_words: dict[str, dict[str, list[anki.cards.Card]]]
    notes_words_familiarity: NotesWordsFamiliarity
    
def get_notes_words_familiarity(notes_reviewed_words_presence_rate:dict[str, dict[str, list[float]]]) -> NotesWordsFamiliarity:
    notes_words_familiarity:NotesWordsFamiliarity = NotesWordsFamiliarity({})
    for field_key in notes_reviewed_words_presence_rate:
        
        field_all_word_presence_scores = [sum(word_scores) for word_scores in notes_reviewed_words_presence_rate[field_key].values()]
        field_avg_word_presence_score = mean(field_all_word_presence_scores)
        field_median_word_presence_score = statistics.median(field_all_word_presence_scores)
        #var_dump({'avg':field_avg_word_score, 'max': max(field_all_word_scores), 'median': field_median_word_score})
        
        if field_key not in notes_words_familiarity:
            notes_words_familiarity[field_key] = {}
        
        for word_token in notes_reviewed_words_presence_rate[field_key]:
            token_values = notes_reviewed_words_presence_rate[field_key][word_token]
            token_familiarity_score = sum(token_values)
            if (token_familiarity_score > field_median_word_presence_score):
                token_familiarity_score = mean([token_familiarity_score, field_median_word_presence_score])
            if (token_familiarity_score > 10*field_median_word_presence_score):
                token_familiarity_score = 10*field_median_word_presence_score
            notes_words_familiarity[field_key][word_token] = token_familiarity_score
            
        max_familiarity = max(notes_words_familiarity[field_key].values())
        #var_dump({'max': max_familiarity, 'avg': avg_familiarity, 'med':median_familiarity})
        
        for word_token in notes_words_familiarity[field_key]:
            rel_score = notes_words_familiarity[field_key][word_token]/max_familiarity
            notes_words_familiarity[field_key][word_token] = rel_score
            
        notes_words_familiarity[field_key] = dict(sorted(notes_words_familiarity[field_key].items(), key=lambda x: x[1], reverse=True))
    return notes_words_familiarity
    
def get_target_cards_corpus_data(target_cards:Iterable[anki.cards.Card], target:Target) -> TargetCorpusData:

    target_fields_by_notes_name = target.getNotes()
    handled_cards = {}
    notes_reviewed_words:dict[str, dict[str, list[anki.cards.Card]]] = {} # words from reviewed cards
    notes_reviewed_words_presence_rate:dict[str, dict[str, list[float]]] = {} # how much words were present in reviewed cards
    
    for card in target_cards:
        card_note = mw.col.getNote(card.nid)
        card_note_type = card_note.model()
        card_has_been_reviewed = card.type == 2 and card.queue != 0 # card is of type 'review' and queue is not 'new'
         
        if card_note_type['name'] not in target_fields_by_notes_name: # note type name is not defined as target
            continue
            
        target_note_fields = target_fields_by_notes_name[card_note_type['name']]
        
        card_note_items_accepted = []
        for field_name, field_val in card_note.items():
            if field_name in target_note_fields.keys():
                
                field_key = str(card_note_type['id'])+" => "+field_name
                
                plain_text = TextProcessing.get_plain_text(field_val).lower()
                field_value_tokenized = TextProcessing.get_word_tokens_from_text(plain_text, target_note_fields[field_name])
                field_value_num_tokens = len(field_value_tokenized)
                
                card_note_items_accepted.append({
                    "field_name": field_name, 
                    "field_value_plain_text": plain_text, 
                    "field_value_tokenized": field_value_tokenized, 
                    "target_language_id": target_note_fields[field_name].lower()
                })
                
                if card_has_been_reviewed:
                    for word_token in field_value_tokenized:
                        # set reviewed words (word has been in reviewed card)
                        if field_key not in notes_reviewed_words:
                            notes_reviewed_words[field_key] = {}
                        if word_token not in notes_reviewed_words[field_key]:
                            notes_reviewed_words[field_key][word_token] = [] 
                        notes_reviewed_words[field_key][word_token].append(card)
                        # set presence_score for reviewed words 
                        if field_key not in notes_reviewed_words_presence_rate:
                            notes_reviewed_words_presence_rate[field_key] = {}
                        if word_token not in notes_reviewed_words_presence_rate[field_key]:
                            notes_reviewed_words_presence_rate[field_key][word_token] = [] 
                        token_presence_score = 1/mean([field_value_num_tokens, 3]) 
                        notes_reviewed_words_presence_rate[field_key][word_token].append(token_presence_score)
                
        handled_cards[card.id] = {'card': card, "accepted_fields": card_note_items_accepted}
            
    notes_words_familiarity = get_notes_words_familiarity(notes_reviewed_words_presence_rate)
            
    #var_dump_log(notes_words_familiarity)

    return {"handled_target_cards": handled_cards, "notes_known_words": notes_reviewed_words, "notes_words_familiarity": notes_words_familiarity}

def ideal_word_count_score(word_count, ideal_num) -> float:

    if word_count < ideal_num:
        m = 7
    else:
        m = 5
    difference = abs(word_count - ideal_num)
    score = 1 / (1 + (difference / ideal_num) ** m)
    return mean([max(0, score), 1])

    
def get_card_ranking(card:anki.cards.Card, cards_corpus_data:TargetCorpusData, word_frequency_lists:WordFrequencyLists) -> float:
    
    card_note = mw.col.getNote(card.nid)
    card_note_type = card_note.model()
    
    card_ranking_factors:dict[str, float] = {}
    
    card_fr_scores:list[float] = [] # Avg frequency of words, avg per field | Card with common words should go up
    card_focus_word_fr_scores:list[float] = [] # Lowest frequency of unknown words, avg per fields | Cards introducing MOSTLY a common word should go up
    # card_words_unfamiliarity_scores:list[float] = [] # | Card with words seen a lot should go down
    # card_words_problematic_occurrence_scores:list[float] = [] # Problematic_occurrence_score of words, avg per field | Cards with problematic words should go up
    # card_words_fresh_occurrence_scores:list[float] = [] # Freshness of words, avg per field | Cards with fresh words (recently matured?) should go up
     
    # get scores per field
    
    accepted_fields = cards_corpus_data['handled_target_cards'][card.id]['accepted_fields']
    fields_highest_fr_unknown_word:list[Tuple] = []
    fields_known_words:list[list[str]] = []
    fields_unknown_words:list[list[str]] = []
    fields_ideal_unknown_words_count:list[float] = []
    fields_ideal_words_count:list[float] = []
    
    for field_data in accepted_fields:
        
        field_fr_score:list[float] = []
        field_highest_fr_unknown_word:Tuple[str, float]  = ("", 0)
        field_known_words:list[str] = []
        field_unknown_words:list[str] = []
        field_key = str(card_note_type['id'])+" => "+field_data['field_name']
        
        for word in field_data['field_value_tokenized']:
            word_fr = word_frequency_lists.getWordFrequency(field_data['target_language_id'], word, 0)
            #word_fr_relative =  
            field_fr_score.append(word_fr)
            if word in cards_corpus_data['notes_known_words'].get(field_key, {}):
                field_known_words.append(word) # word is known
            else:
                field_unknown_words.append(word)
                if word_fr > 0 and (field_highest_fr_unknown_word[1] == 0 or word_fr < field_highest_fr_unknown_word[1]):
                    field_highest_fr_unknown_word = (word, word_fr) 

        # set known and unknown words
        fields_known_words.append(field_known_words)
        fields_unknown_words.append(field_unknown_words)
        
        # ideal unknown words count
        num_unknown_words = len(field_unknown_words)
        ideal_unknown_words_count_rate = 0
        if (num_unknown_words > 0):
            ideal_unknown_words_count_rate = min(1, abs( 0-(1.5*1/min(num_unknown_words, 10)) ) )
        fields_ideal_unknown_words_count.append(ideal_unknown_words_count_rate)
        
        # ideal word count
        fields_ideal_words_count.append(ideal_word_count_score(len(field_data['field_value_tokenized']), 4))
        
        # highest fr unknown word
        fields_highest_fr_unknown_word.append(field_highest_fr_unknown_word)
        card_focus_word_fr_scores.append(field_highest_fr_unknown_word[1]) 
        card_fr_scores.append(mean(field_fr_score))  
     
    # define ranking factors for card, based on avg of fields
    
    card_ranking_factors['words_frequency_score'] = mean(card_fr_scores) #todo: make relative to num words?  
    card_ranking_factors['focus_word_frequency_score'] = mean(card_focus_word_fr_scores) #todo: make relative to num words?  
    card_ranking_factors['ideal_unknown_word_count'] = mean(fields_ideal_unknown_words_count)
    card_ranking_factors['ideal_word_count'] = mean(fields_ideal_words_count)
    # card_ranking_factors['words_problematic_occurrence_scores'] = mean(card_words_problematic_occurrence_scores) 
    # card_ranking_factors['words_fresh_occurrence_scores'] = mean(card_words_fresh_occurrence_scores) 
 
    # final ranking
    card_ranking = mean(card_ranking_factors.values())

    # set data in card fields 
    if 'fm_debug_info' in card_note:
        debug_info = {
            'fr_scores': card_fr_scores, 
            'focus_fr_scores': card_focus_word_fr_scores, 
            'ideal_unknown_word_count': fields_ideal_unknown_words_count,
            'ideal_word_count': fields_ideal_words_count,
            'fields_highest_fr_unknown_word': fields_highest_fr_unknown_word,
        }
        card_note['fm_debug_info'] = pprint.pformat(debug_info, width=120, sort_dicts=False).replace('\n', '<br>')
        card_note.flush()
    if 'fm_known_words' in card_note:
        card_note['fm_known_words'] = pprint.pformat(fields_known_words).replace('\n', '<br>')
        card_note.flush()
    if 'fm_unknown_words' in card_note:
        card_note['fm_unknown_words'] = pprint.pformat(fields_unknown_words).replace('\n', '<br>')
        card_note.flush()
    
    return card_ranking

 
def reorder_target_cards(target:Target, word_frequency_lists:WordFrequencyLists) -> bool:
    target_search_query = target.construct_search_query()
    if "note:" not in target_search_query:
        showInfo("No valid note type defined. At least one note is required for reordering!")
        return False
    
    # Get results for target
    
    target_all_cards_ids = mw.col.find_cards(target_search_query, order="c.due asc")
    target_all_cards = [mw.col.get_card(card_id) for card_id in target_all_cards_ids]
    
    target_new_cards = [card for card in target_all_cards if card.queue == 0]
    target_new_cards_ids = [card.id for card in target_new_cards]

    showInfo("Reordering {} new cards in a collection of {} cards!".format(len(target_new_cards_ids), len(target_all_cards))) 
    
    cards_corpus_data = get_target_cards_corpus_data(target_all_cards, target)  
    
    #var_dump({'num_cards': len(target_cards), 'num_new_cards': len(target_new_cards), 'query': target_search_query})
    
    # Sort cards
    sorted_cards = sorted(target_new_cards, key=lambda card: get_card_ranking(card, cards_corpus_data, word_frequency_lists), reverse=True)
    sorted_card_ids = [card.id for card in sorted_cards]

    # Avoid making unnecessary changes
    if target_new_cards_ids == sorted_card_ids:
        showInfo("No card needed sorting!")
        return False
    
    # Reposition cards and apply changes
    mw.col.sched.forgetCards(sorted_card_ids)
    mw.col.sched.reposition_new_cards(
        card_ids=sorted_card_ids,
        starting_from=0, step_size=1,
        randomize=False, shift_existing=True
    )
    
    showInfo("Done with sorting!")
    
    return True
    
def execute_reorder(fm_window:FrequencyManMainWindow):
    
    frequency_lists_dir = os.path.join(os.path.dirname(__file__), 'user_files', 'frequency_lists')
    word_frequency_list = WordFrequencyLists(frequency_lists_dir)
    
    for target in fm_window.target_data:
        reorder_target_cards(target, word_frequency_list)
    

def create_tab_sort_cards(fm_window:FrequencyManMainWindow):
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
    

def create_tab_word_overview(fm_window:FrequencyManMainWindow):
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

add_frequencyman_menu_option_to_anki_tools_menu()


