from statistics import mean, median
from typing import Any, Dict, Iterable, NewType
import anki.cards

from ..frequencyman.target_list import Target
from ..frequencyman.text_processing import TextProcessing


class TargetCorpusData:
    """
    Class representing corpus data from target cards.
    """
    
    handled_cards: dict[int, dict[str, Any]]
    notes_known_words: dict[str, dict[str, list[anki.cards.Card]]]
    
    notes_reviewed_words_presence_rate: dict[str, dict[str, list[float]]]
    notes_reviewed_words_familiarity: dict[str, dict[str, float]]
    
    def __init__(self):
        
        self.handled_cards = {}
        self.notes_known_words = {} # words from reviewed cards
        
        self.notes_reviewed_words_presence_rate = {} # how much words are present in reviewed cards
        self.notes_reviewed_words_familiarity = {} # how much words are present in reviewed cards

    def __set_notes_words_familiarity(self) -> None:
        """
        Set the familiarity score for each word per note, based on word presence.
        """
        for field_key in self.notes_reviewed_words_presence_rate:
            
            field_all_word_presence_scores = [sum(word_scores) for word_scores in self.notes_reviewed_words_presence_rate[field_key].values()]
            field_avg_word_presence_score = mean(field_all_word_presence_scores)
            field_median_word_presence_score = median(field_all_word_presence_scores)
            #var_dump({'avg':field_avg_word_score, 'max': max(field_all_word_scores), 'median': field_median_word_score})
            
            if field_key not in self.notes_reviewed_words_familiarity:
                self.notes_reviewed_words_familiarity[field_key] = {}
            
            for word_token in self.notes_reviewed_words_presence_rate[field_key]:
                token_values = self.notes_reviewed_words_presence_rate[field_key][word_token]
                token_familiarity_score = sum(token_values)
                if (token_familiarity_score > field_median_word_presence_score):
                    token_familiarity_score = mean([token_familiarity_score, field_median_word_presence_score])
                if (token_familiarity_score > 10*field_median_word_presence_score):
                    token_familiarity_score = 10*field_median_word_presence_score
                self.notes_reviewed_words_familiarity[field_key][word_token] = token_familiarity_score
                
            max_familiarity = max(self.notes_reviewed_words_familiarity[field_key].values())
            #var_dump({'max': max_familiarity, 'avg': avg_familiarity, 'med':median_familiarity})
            
            for word_token in self.notes_reviewed_words_familiarity[field_key]:
                rel_score = self.notes_reviewed_words_familiarity[field_key][word_token]/max_familiarity
                self.notes_reviewed_words_familiarity[field_key][word_token] = rel_score
                
            self.notes_reviewed_words_familiarity[field_key] = dict(sorted(self.notes_reviewed_words_familiarity[field_key].items(), key=lambda x: x[1], reverse=True))
   
    
    def load_data(self, target_cards:Iterable[anki.cards.Card], target:Target) -> None:
        """
        Load data into the TargetCorpusData object
        """
        target_fields_by_notes_name = target.get_notes()
        
        for card in target_cards:
            #card_note = mw.col.getNote(card.nid)
            card_note = card.note
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
                            if field_key not in self.notes_known_words:
                                self.notes_known_words[field_key] = {}
                            if word_token not in self.notes_known_words[field_key]:
                                self.notes_known_words[field_key][word_token] = [] 
                            self.notes_known_words[field_key][word_token].append(card)
                            # set presence_score for reviewed words 
                            if field_key not in self.notes_reviewed_words_presence_rate:
                                self.notes_reviewed_words_presence_rate[field_key] = {}
                            if word_token not in self.notes_reviewed_words_presence_rate[field_key]:
                                self.notes_reviewed_words_presence_rate[field_key][word_token] = [] 
                            token_presence_score = 1/mean([field_value_num_tokens, 3]) 
                            self.notes_reviewed_words_presence_rate[field_key][word_token].append(token_presence_score)
                    
            self.handled_cards[card.id] = {'card': card, "accepted_fields": card_note_items_accepted}
                
        self.__set_notes_words_familiarity()
