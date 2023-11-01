from statistics import mean
from typing import Tuple

import anki.cards
from anki.collection import Collection

from ..frequencyman.utilities import *
from ..frequencyman.target_corpus_data import TargetCorpusData
from ..frequencyman.word_frequency_list import WordFrequencyLists


class CardRanker:
    
    def __init__(self, cards_corpus_data:TargetCorpusData, word_frequency_lists:WordFrequencyLists, col:Collection) -> None:
        self.cards_corpus_data = cards_corpus_data
        self.word_frequency_lists = word_frequency_lists
        self.col = col
        

    @staticmethod
    def card_field_ideal_word_count_score(word_count:int, ideal_num:int) -> float:

        if word_count < ideal_num:
            m = 7
        else:
            m = 5
        difference = abs(word_count - ideal_num)
        score = 1 / (1 + (difference / ideal_num) ** m)
        return mean([max(0, score), 1])

        
    def calc_card_ranking(self, card:anki.cards.Card) -> float:
        
        card_note = self.col.get_note(card.nid)
        card_note_type_id = card_note.mid
        assert isinstance(card_note_type_id, int)
        assert card_note_type_id != 0
        
        card_ranking_factors:dict[str, float] = {}
        
        fields_fr_scores:list[float] = [] # Avg frequency of words, avg per field | Card with common words should go up
        fields_highest_fr_unseen_word_scores:list[float] = [] # Lowest frequency of unseen words, avg per fields | Cards introducing MOSTLY a common word should go up
        # fields_words_unfamiliarity_scores:list[float] = [] # | Card with words seen a lot should go down
        # fields_words_fresh_occurrence_scores:list[float] = [] # Freshness of words, avg per field | Cards with fresh words (recently matured?) should go up
        
        # get scores per field
        
        accepted_fields = self.cards_corpus_data.handled_cards[card.id]['accepted_fields']
        fields_highest_fr_unseen_word:list[Tuple[str, float]] = []
        fields_seen_words:list[list[str]] = []
        fields_unseen_words:list[list[str]] = []
        fields_ideal_unseen_words_count_scores:list[float] = []
        fields_ideal_words_count_scores:list[float] = [] 
        
        for field_data in accepted_fields:
            
            field_fr_scores:list[float] = []
            field_seen_words:list[str] = []
            field_unseen_words:list[str] = []
            field_highest_fr_unseen_word:Tuple[str, float]  = ("", 0)
            field_key = str(card_note_type_id)+" => "+field_data['field_name']
            
            for word in field_data['field_value_tokenized']:
                word_fr = self.word_frequency_lists.getWordFrequency(field_data['target_language_id'], word, 0)

                #word_lexical_discrepancy_rating = (word_fr - familiarity)
                #word_novelty_rating = (1-familiarity) notes_reviewed_words_familiarity
                #card_perplexity_rating = avg( word_novelty_rating/card_word_count where word_novelty_rating < 0.5 ) /
                field_fr_scores.append(word_fr)
                if word in self.cards_corpus_data.notes_reviewed_words.get(field_key, {}):
                    field_seen_words.append(word) # word seen, word exist in at least one reviewed card
                else:
                    field_unseen_words.append(word)
                    if word_fr > 0 and (field_highest_fr_unseen_word[1] == 0 or word_fr < field_highest_fr_unseen_word[1]):
                        field_highest_fr_unseen_word = (word, word_fr) 

            # set known and unseen words
            fields_seen_words.append(field_seen_words)
            fields_unseen_words.append(field_unseen_words)
            
            # ideal unseen words count
            num_unseen_words = len(field_unseen_words)
            ideal_unseen_words_count_score = 0
            if (num_unseen_words > 0):
                ideal_unseen_words_count_score = min(1, abs( 0-(1.5*1/min(num_unseen_words, 10)) ) )
            fields_ideal_unseen_words_count_scores.append(ideal_unseen_words_count_score)
            
            # ideal word count
            fields_ideal_words_count_scores.append(self.card_field_ideal_word_count_score(len(field_data['field_value_tokenized']), 4))
            
            # highest fr unseen word
            fields_highest_fr_unseen_word.append(field_highest_fr_unseen_word)
            fields_highest_fr_unseen_word_scores.append(field_highest_fr_unseen_word[1]) 
            fields_fr_scores.append(mean(field_fr_scores))  
        
        # define ranking factors for card, based on avg of fields
        
        card_ranking_factors['words_frequency_score'] = mean(fields_fr_scores) #todo: make relative to num words?  
        card_ranking_factors['focus_word_frequency_score'] = mean(fields_highest_fr_unseen_word_scores) #todo: make relative to num words?  
        card_ranking_factors['ideal_unseen_word_count'] = mean(fields_ideal_unseen_words_count_scores)
        card_ranking_factors['ideal_word_count'] = mean(fields_ideal_words_count_scores)

        # card_ranking_factors['words_fresh_occurrence_scores'] = mean(fields_words_fresh_occurrence_scores) 
    
        # final ranking
        card_ranking = mean(card_ranking_factors.values())

        # set data in card fields 
        if 'fm_debug_info' in card_note:
            debug_info = {
                'fr_scores': fields_fr_scores, 
                'focus_fr_scores': fields_highest_fr_unseen_word_scores, 
                'ideal_unseen_word_count': fields_ideal_unseen_words_count_scores,
                'ideal_word_count': fields_ideal_words_count_scores,
                'fields_highest_fr_unseen_word': fields_highest_fr_unseen_word,
            }
            card_note['fm_debug_info'] = pprint.pformat(debug_info, width=120, sort_dicts=False).replace('\n', '<br>')
            card_note.flush()
        if 'fm_seen_words' in card_note:
            card_note['fm_seen_words'] = pprint.pformat(fields_seen_words).replace('\n', '<br>')
            card_note.flush()
        if 'fm_unseen_words' in card_note:
            card_note['fm_unseen_words'] = pprint.pformat(fields_unseen_words).replace('\n', '<br>')
            card_note.flush()
        
        return card_ranking