from statistics import mean, median
from typing import Iterable, TypedDict

import anki.cards
from anki.collection import Collection
from anki.cards import CardId, Card

from .lib.utilities import *
from .target_list import Target
from .text_processing import TextProcessing

HandledCardsFields = TypedDict('HandledCardsFields', {'card': Card, 'accepted_fields': list[dict[str, str]]})


class TargetCorpusData:
    """
    Class representing corpus data from target cards.
    """
    
    handled_cards: dict[CardId, HandledCardsFields]
    
    notes_reviewed_words: dict[str, dict[str, list[Card]]]
    notes_reviewed_words_occurrences: dict[str, dict[str, list[float]]] # list because a word can occur multiple times in a field
    notes_reviewed_words_familiarity: dict[str, dict[str, float]]
    
    def __init__(self):
        
        self.handled_cards = {}
        
        self.notes_reviewed_words = {} # words and the cards they they occur in, per "note+field"
        self.notes_reviewed_words_occurrences = {} # how much a word occurs in reviewed cards, per "note+field"
        self.notes_reviewed_words_familiarity = {} # how much words are present in reviewed cards, per "note+field"

    def __set_notes_words_familiarity(self) -> None:
        """
        Set the familiarity score for each word per note, based on word presence.
        """
        for field_key in self.notes_reviewed_words_occurrences:
            
            field_all_word_presence_scores = [sum(word_scores) for word_scores in self.notes_reviewed_words_occurrences[field_key].values()]
            field_avg_word_presence_score = mean(field_all_word_presence_scores)
            field_median_word_presence_score = median(field_all_word_presence_scores)
            
            if field_key not in self.notes_reviewed_words_familiarity:
                self.notes_reviewed_words_familiarity[field_key] = {}
            
            for word_token in self.notes_reviewed_words_occurrences[field_key]:
                
                word_presence_scores = self.notes_reviewed_words_occurrences[field_key][word_token]
                word_familiarity_score = sum(word_presence_scores) # todo: also incorporate cards review time?
                if (word_familiarity_score > field_median_word_presence_score): # flatten the top half
                    word_familiarity_score = mean([word_familiarity_score, field_median_word_presence_score])
                if (word_familiarity_score > 10*field_median_word_presence_score):
                    word_familiarity_score = 10*field_median_word_presence_score
                
                self.notes_reviewed_words_familiarity[field_key][word_token] = word_familiarity_score
                
            max_familiarity = max(self.notes_reviewed_words_familiarity[field_key].values())

            # make scores values relative
            for word_token in self.notes_reviewed_words_familiarity[field_key]:
                rel_score = self.notes_reviewed_words_familiarity[field_key][word_token]/max_familiarity
                self.notes_reviewed_words_familiarity[field_key][word_token] = rel_score
                
            # sort in descending order (todo: can be removed?)
            self.notes_reviewed_words_familiarity[field_key] = dict(sorted(self.notes_reviewed_words_familiarity[field_key].items(), key=lambda x: x[1], reverse=True))
   
    
    def create_data(self, target_cards:Iterable[Card], target:Target, col:Collection) -> None:
        """
        Create corpus data for the given target and its cards.
        """
        target_fields_by_notes_name = target.get_notes()
        
        for card in target_cards:
            
            assert isinstance(card.nid, int) and card.nid != 0
            card_note = col.get_note(card.nid)
            
            card_note_type = col.models.get(card_note.mid)
            
            if (card_note_type is None):
                raise Exception(f"Card note type not found for card.nid={card_note.mid}!")
            if card_note_type['name'] not in target_fields_by_notes_name: # note type name is not defined as target
                continue

            card_has_been_reviewed = card.type == 2 and card.queue != 0 # card is of type 'review' and queue is not 'new'
                
            target_note_fields = target_fields_by_notes_name[card_note_type['name']]
            
            card_note_items_accepted = []
            for field_name, field_val in card_note.items():
                if field_name in target_note_fields.keys():
                    
                    field_key = str(card_note_type['id'])+" => "+field_name
                    
                    lang_key = target_note_fields[field_name].lower()
                    lang_id = lang_key
                    if (len(lang_id) > 3 and lang_id[2] == '_'):
                        lang_id = lang_id[:2]
                    
                    plain_text = TextProcessing.get_plain_text(field_val).lower()
                    field_value_tokenized = TextProcessing.get_word_tokens_from_text(plain_text, lang_id)
                    field_value_num_tokens = len(field_value_tokenized)
                    
                    card_note_items_accepted.append({
                        "field_name": field_name, 
                        "field_value_plain_text": plain_text, 
                        "field_value_tokenized": field_value_tokenized, 
                        "target_language_key": lang_key,
                        "target_language_id": lang_id
                    })
                    
                    if card_has_been_reviewed:
                        for word_token in field_value_tokenized:
                            # set reviewed words (word has been in reviewed card)
                            if field_key not in self.notes_reviewed_words:
                                self.notes_reviewed_words[field_key] = {}
                            if word_token not in self.notes_reviewed_words[field_key]:
                                self.notes_reviewed_words[field_key][word_token] = [] 
                            self.notes_reviewed_words[field_key][word_token].append(card)
                            # set presence_score for reviewed words 
                            if field_key not in self.notes_reviewed_words_occurrences:
                                self.notes_reviewed_words_occurrences[field_key] = {}
                            if word_token not in self.notes_reviewed_words_occurrences[field_key]:
                                self.notes_reviewed_words_occurrences[field_key][word_token] = [] 
                            token_presence_score = 1/mean([field_value_num_tokens, 3]) 
                            self.notes_reviewed_words_occurrences[field_key][word_token].append(token_presence_score)
                    
            self.handled_cards[card.id] = {'card': card, "accepted_fields": card_note_items_accepted}
                
        self.__set_notes_words_familiarity()
