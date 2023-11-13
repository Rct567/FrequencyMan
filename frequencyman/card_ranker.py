from statistics import mean
from typing import Tuple

from anki.cards import Card, CardId
from anki.notes import Note, NoteId
from anki.collection import Collection

from .lib.utilities import *
from .target_corpus_data import TargetCorpusData
from .word_frequency_list import WordFrequencyLists


class CardRanker:

    modified_dirty_notes: list[Note]

    def __init__(self, cards_corpus_data: TargetCorpusData, word_frequency_lists: WordFrequencyLists, col: Collection) -> None:
        self.cards_corpus_data = cards_corpus_data
        self.word_frequency_lists = word_frequency_lists
        self.col = col
        self.modified_dirty_notes = []

    @staticmethod
    def card_field_ideal_word_count_score(word_count: int, ideal_num: int) -> float:

        if word_count < ideal_num:
            m = 7
        else:
            m = 5
        difference = abs(word_count - ideal_num)
        score = 1 / (1 + (difference / ideal_num) ** m)
        return mean([max(0, score), 1])

    @staticmethod
    def calc_ideal_unseen_words_count_score(num_unseen_words:int) -> float:
        score = 0
        if (num_unseen_words > 0):
            score = min(1, abs(0-(1.5*1/min(num_unseen_words, 10))))
        return score


    def calc_cards_ranking(self, cards: list[Card]) -> dict[CardId, float]:

        notes_from_cards: dict[NoteId, Note] = {}
        cards_per_note: dict[NoteId, list[Card]] = {} # future use?

        notes_rankings: dict[NoteId, float] = {}
        card_rankings: dict[CardId, float] = {}

        # card ranking is calculates per note (which may have different card, but same ranking)

        for card in cards:
            if card.nid not in notes_from_cards:
                notes_from_cards[card.nid] = self.col.get_note(card.nid)
                if card.nid not in cards_per_note:
                    cards_per_note[card.nid] = []
                cards_per_note[card.nid].append(card)

        for note_id, note in notes_from_cards.items():
            notes_rankings[note_id] = self.calc_card_note_ranking(note, cards_per_note[note_id])

        for card in cards:
            card_rankings[card.id] = notes_rankings[card.nid]

        return card_rankings

    def calc_card_note_ranking(self, note: Note, note_cards: list[Card]) -> float:

        card_ranking_factors: dict[str, float] = {}

        fields_fr_scores: list[float] = []  # Avg frequency of words, avg per field | Card with common words should go up
        fields_lowest_fr_unseen_word_scores: list[float] = []  # Lowest frequency of unseen words, avg per fields | Cards introducing MOSTLY a common word should go up
        # fields_words_unfamiliarity_scores:list[float] = [] # | Card with words seen a lot should go down
        # fields_words_fresh_occurrence_scores:list[float] = [] # Freshness of words, avg per field | Cards with fresh words (recently matured?) should go up

        # get scores per field
        fields_in_target = self.cards_corpus_data.handled_notes[note.id]
        fields_words_fr_scores: list[dict[str, float]] = []
        fields_lowest_fr_unseen_word: list[Tuple[str, float]] = []
        fields_lowest_fr_word: list[Tuple[str, float]] = []
        fields_seen_words: list[list[str]] = []
        fields_unseen_words: list[list[str]] = []
        fields_ideal_unseen_words_count_scores: list[float] = []
        fields_ideal_words_count_scores: list[float] = []

        for field_data in fields_in_target:

            field_fr_scores: list[float] = []
            field_words_fr_scores: dict[str, float] = {}
            field_seen_words: list[str] = []
            field_unseen_words: list[str] = []
            field_lowest_fr_unseen_word: Tuple[str, float] = ("", 0)
            field_lowest_fr_word: Tuple[str, float] = ("", 0)
            field_key = field_data.field_key

            if not field_key.startswith(str(note.mid)):
                raise Exception("Card note type id is not matching!?")

            for word in field_data.field_value_tokenized:

                word_fr = self.word_frequency_lists.get_word_frequency(field_data.target_language_key, word, 0)
                # word_familiarity = self.cards_corpus_data.notes_reviewed_words_familiarity[field_key][word]
                # word_lexical_discrepancy_rating = (word_fr - word_familiarity) aka unfamiliarity of high frequency words
                # word_novelty_rating = (1-word_familiarity) notes_reviewed_words_familiarity
                # card_perplexity_rating = avg( word_novelty_rating/card_word_count where word_novelty_rating < 0.5 ) /

                field_fr_scores.append(word_fr)
                field_words_fr_scores[word] = word_fr

                # lowest fr word
                if field_lowest_fr_word[0] == "" or word_fr < field_lowest_fr_word[1]:
                    field_lowest_fr_word = (word, word_fr)

                # set seen, unseen and lowest fr unseen
                if word in self.cards_corpus_data.notes_reviewed_words.get(field_key, {}):
                    field_seen_words.append(word)  # word seen, word exist in at least one reviewed card
                else:
                    field_unseen_words.append(word)
                    if field_lowest_fr_unseen_word[0] == "" or word_fr < field_lowest_fr_unseen_word[1]:
                        field_lowest_fr_unseen_word = (word, word_fr)

            # set known and unseen words
            fields_seen_words.append(field_seen_words)
            fields_unseen_words.append(field_unseen_words)

            #  set lowest frequency word
            fields_lowest_fr_word.append(field_lowest_fr_word)

            fields_words_fr_scores.append(field_words_fr_scores)

            # ideal unseen words count
            num_unseen_words = len(field_unseen_words)
            fields_ideal_unseen_words_count_scores.append(self.calc_ideal_unseen_words_count_score(num_unseen_words))

            # ideal word count
            fields_ideal_words_count_scores.append(self.card_field_ideal_word_count_score(len(field_data.field_value_tokenized), 4))

            # lowest fr unseen word
            fields_lowest_fr_unseen_word.append(field_lowest_fr_unseen_word)
            fields_lowest_fr_unseen_word_scores.append(field_lowest_fr_unseen_word[1])
            if (len(field_fr_scores) > 0):
                fields_fr_scores.append(mean(field_fr_scores))
            else:
                fields_fr_scores.append(0)

        # define ranking factors for card, based on avg of fields

        card_ranking_factors['words_frequency_score'] = mean(fields_fr_scores)  # todo: make relative to num words?
        card_ranking_factors['lowest_fr_unseen_word_scores'] = mean(fields_lowest_fr_unseen_word_scores)  # todo: make relative to num words?
        card_ranking_factors['ideal_unseen_word_count'] = mean(fields_ideal_unseen_words_count_scores)
        card_ranking_factors['ideal_word_count'] = mean(fields_ideal_words_count_scores)
        # card_ranking_factors['words_fresh_occurrence_scores'] = mean(fields_words_fresh_occurrence_scores)

        # final ranking
        card_ranking = mean(card_ranking_factors.values())

        # set data in card fields
        update_note = False
        if 'fm_debug_info' in note:
            fields_words_fr_scores_sorted = [dict(sorted(d.items(), key=lambda item: item[1], reverse=True)) for d in fields_words_fr_scores]
            debug_info = {
                'fr_scores': fields_fr_scores,
                'lowest_fr_unseen_word': fields_lowest_fr_unseen_word,
                'lowest_fr_unseen_word_scores': fields_lowest_fr_unseen_word_scores,
                'ideal_unseen_words_count_scores': fields_ideal_unseen_words_count_scores,
                'ideal_word_count': fields_ideal_words_count_scores,
                'words_fr_scores': fields_words_fr_scores_sorted
            }
            note['fm_debug_info'] = ''
            for k, var in debug_info.items():
                note['fm_debug_info'] += k+": " + pprint.pformat(var, sort_dicts=False)+"<br />\n"
            update_note = True
        if 'fm_seen_words' in note:
            printed_fields_seen_words = [", ".join(words) for words in fields_seen_words]
            note['fm_seen_words'] = " | ".join(printed_fields_seen_words)
            update_note = True
        if 'fm_unseen_words' in note:
            printed_fields_unseen_words = [", ".join(words) for words in fields_unseen_words]
            note['fm_unseen_words'] = " | ".join(printed_fields_unseen_words)
            update_note = True
        if 'fm_lowest_fr_word' in note:
            printed_fields_lowest_fr_word = [f"{word} ({fr:.2f})" for (word, fr) in fields_lowest_fr_word]
            note['fm_lowest_fr_word'] = " | ".join(printed_fields_lowest_fr_word)
            update_note = True

        if update_note:
            self.modified_dirty_notes.append(note)

        return card_ranking
