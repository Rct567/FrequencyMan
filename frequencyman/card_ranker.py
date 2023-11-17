from dataclasses import dataclass, field
from statistics import mean
from typing import Tuple

from anki.cards import Card, CardId
from anki.notes import Note, NoteId
from anki.collection import Collection

from .text_processing import WordToken
from .lib.utilities import *
from .target_corpus_data import FieldKey, TargetCorpusData, TargetFieldData
from .word_frequency_list import WordFrequencyLists


@dataclass
class FieldMetrics:
    fr_scores: list[float] = field(default_factory=list)
    words_fr_scores: dict[WordToken, float] = field(default_factory=dict)

    ld_scores: list[float] = field(default_factory=list)
    words_ld_scores: dict[WordToken, float] = field(default_factory=dict)

    seen_words: list[WordToken] = field(default_factory=list)
    unseen_words: list[WordToken] = field(default_factory=list)

    lowest_fr_unseen_word: Tuple[WordToken, float] = (WordToken(""), 0)
    lowest_fr_word: Tuple[WordToken, float] = (WordToken(""), 0)

    highest_ld_word: Tuple[WordToken, float] = (WordToken(""), 0)


@dataclass
class FieldsMetrics:
    words_fr_scores: list[dict[WordToken, float]] = field(default_factory=list)
    words_ld_scores: list[dict[WordToken, float]] = field(default_factory=list)

    lowest_fr_unseen_word: list[Tuple[WordToken, float]] = field(default_factory=list)
    lowest_fr_word: list[Tuple[WordToken, float]] = field(default_factory=list)

    highest_ld_word: list[Tuple[WordToken, float]] = field(default_factory=list)

    seen_words: list[list[WordToken]] = field(default_factory=list)
    unseen_words: list[list[WordToken]] = field(default_factory=list)

    ideal_unseen_words_count_scores: list[float] = field(default_factory=list)
    ideal_words_count_scores: list[float] = field(default_factory=list)

    fr_scores: list[float] = field(default_factory=list)  # Avg frequency of words (per field) | Card with common words should go up
    ld_scores: list[float] = field(default_factory=list)

    lowest_fr_unseen_word_scores: list[float] = field(default_factory=list)  # Lowest frequency of unseen words (per fields) | Cards introducing MOSTLY a common word should go up
    highest_ld_word_scores: list[float] = field(default_factory=list)  # Highest ld score, (per field)  

    # fields_words_low_familiarity_scores:list[float] = [] # | Card with words seen rarely should go up
    # fields_words_fresh_occurrence_scores:list[float] = [] # Freshness of words, avg per field | Cards with fresh words (recently matured?) should go up


class CardRanker:

    modified_dirty_notes: list[Note]

    def __init__(self, cards_corpus_data: TargetCorpusData, word_frequency_lists: WordFrequencyLists, col: Collection) -> None:
        self.cards_corpus_data = cards_corpus_data
        self.word_frequency_lists = word_frequency_lists
        self.col = col
        self.modified_dirty_notes = []

    @staticmethod
    def __card_field_ideal_word_count_score(word_count: int, ideal_num: int) -> float:

        if word_count < ideal_num:
            m = 7
        else:
            m = 5
        difference = abs(word_count - ideal_num)
        score = 1 / (1 + (difference / ideal_num) ** m)
        return mean([max(0, score), 1])

    @staticmethod
    def __calc_ideal_unseen_words_count_score(num_unseen_words: int) -> float:
        if (num_unseen_words < 1):
            return 0.8
        score = min(1, abs(0-(1.6*1/min(num_unseen_words, 10))))
        return score

    def calc_cards_ranking(self, cards: list[Card]) -> dict[CardId, float]:

        notes_from_cards: dict[NoteId, Note] = {}
        cards_per_note: dict[NoteId, list[Card]] = {}  # future use?

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
            notes_rankings[note_id] = self.__calc_card_note_ranking(note, cards_per_note[note_id])

        for card in cards:
            card_rankings[card.id] = notes_rankings[card.nid]

        return card_rankings

    def __calc_card_note_ranking(self, note: Note, note_cards: list[Card]) -> float:

        # get scores per field
        note_fields_defined_in_target = self.cards_corpus_data.fields_per_card_note[note.id]
        note_metrics = FieldsMetrics()

        for field_data in note_fields_defined_in_target:

            field_key = field_data.field_key

            if not field_key.startswith(str(note.mid)):
                raise Exception("Card note type id is not matching!?")

            # get metrics for field
            field_metrics = self.__get_field_metrics_from_data(field_data, field_key)

            # set known and unseen words
            note_metrics.seen_words.append(field_metrics.seen_words)
            note_metrics.unseen_words.append(field_metrics.unseen_words)

            #  set lowest frequency word
            note_metrics.lowest_fr_word.append(field_metrics.lowest_fr_word)

            # lowest fr unseen word
            note_metrics.lowest_fr_unseen_word.append(field_metrics.lowest_fr_unseen_word)
            note_metrics.lowest_fr_unseen_word_scores.append(field_metrics.lowest_fr_unseen_word[1])

            #  set lowest ld word
            note_metrics.highest_ld_word.append(field_metrics.highest_ld_word)
            note_metrics.highest_ld_word_scores.append(field_metrics.highest_ld_word[1])

            # fr for every word
            note_metrics.words_fr_scores.append(field_metrics.words_fr_scores)

            # ld for every word
            note_metrics.words_ld_scores.append(field_metrics.words_ld_scores)

            # ideal unseen words count
            num_unseen_words = len(field_metrics.unseen_words)
            note_metrics.ideal_unseen_words_count_scores.append(self.__calc_ideal_unseen_words_count_score(num_unseen_words))

            # ideal word count
            note_metrics.ideal_words_count_scores.append(self.__card_field_ideal_word_count_score(len(field_data.field_value_tokenized), 4))

            # fr score
            if (len(field_metrics.fr_scores) > 0):
                note_metrics.fr_scores.append(mean(field_metrics.fr_scores))
            else:
                note_metrics.fr_scores.append(0)

            # ld score
            if (len(field_metrics.ld_scores) > 0):
                note_metrics.ld_scores.append(mean(field_metrics.ld_scores))
            else:
                note_metrics.ld_scores.append(0)

        # define ranking factors for note, based on avg of fields

        note_ranking_factors: dict[str, float] = {}
        note_ranking_factors['words_ld_score'] = mean(note_metrics.ld_scores)
        note_ranking_factors['highest_ld_word_scores'] = mean(note_metrics.highest_ld_word_scores)

        note_ranking_factors['lowest_fr_unseen_word_scores'] = mean(note_metrics.lowest_fr_unseen_word_scores)

        note_ranking_factors['ideal_unseen_word_count'] = mean(note_metrics.ideal_unseen_words_count_scores)
        note_ranking_factors['ideal_word_count'] = mean(note_metrics.ideal_words_count_scores)

        # not needed anymore: note_ranking_factors['words_fr_score'] = mean(note_metrics.fr_scores)
        # card_ranking_factors['words_fresh_occurrence_scores'] = mean(fields_words_fresh_occurrence_scores)

        # final ranking
        note_ranking = mean(note_ranking_factors.values())

        # Set meta data that will be saved in note fields
        self.__set_fields_meta_data_for_note(note, note_metrics)

        # done
        return note_ranking

    def __get_field_metrics_from_data(self, field_data: TargetFieldData, field_key: FieldKey) -> FieldMetrics:

        field_metrics = FieldMetrics()

        for word in field_data.field_value_tokenized:

            word_fr = self.word_frequency_lists.get_word_frequency(field_data.target_language_key, word, 0)
            word_ld = self.cards_corpus_data.get_words_lexical_discrepancy(field_key, word)  # unfamiliarity of high frequency words
            # word_novelty_rating = (1-word_familiarity) notes_reviewed_words_familiarity
            # card_perplexity_rating = avg( word_novelty_rating/card_word_count where word_novelty_rating < 0.5 ) /

            # todo: lexical_discrepancy_rating and card_perplexity_sweetspot_rating

            field_metrics.fr_scores.append(word_fr)
            field_metrics.words_fr_scores[word] = word_fr

            field_metrics.ld_scores.append(word_ld)
            field_metrics.words_ld_scores[word] = word_ld

            # lowest fr word
            if field_metrics.lowest_fr_word[0] == "" or word_fr < field_metrics.lowest_fr_word[1]:
                field_metrics.lowest_fr_word = (word, word_fr)

            # highest ld word
            if field_metrics.highest_ld_word[0] == "" or word_ld > field_metrics.highest_ld_word[1]:
                field_metrics.highest_ld_word = (word, word_ld)

            # set seen, unseen and lowest fr unseen
            if word in self.cards_corpus_data.notes_reviewed_words.get(field_key, {}):
                field_metrics.seen_words.append(word)  # word seen, word exist in at least one reviewed card
            else:
                field_metrics.unseen_words.append(word)
                if field_metrics.lowest_fr_unseen_word[0] == "" or word_fr < field_metrics.lowest_fr_unseen_word[1]:
                    field_metrics.lowest_fr_unseen_word = (word, word_fr)

        return field_metrics

    def __set_fields_meta_data_for_note(self, note: Note, note_metrics: FieldsMetrics):

        # set data in card fields
        update_note = False
        if 'fm_debug_info' in note:
            fields_words_fr_scores_sorted = [dict(sorted(d.items(), key=lambda item: item[1], reverse=True)) for d in note_metrics.words_fr_scores]
            fields_words_ld_scores_sorted = [dict(sorted(d.items(), key=lambda item: item[1], reverse=True)) for d in note_metrics.words_ld_scores]
            debug_info = {
                #'ld_score': mean(note_metrics.ld_scores),
                'ld_scores': note_metrics.ld_scores,
                'fr_scores': note_metrics.fr_scores,
                'lowest_fr_unseen_word': note_metrics.lowest_fr_unseen_word,
                'highest_ld_word': note_metrics.highest_ld_word,
                'ideal_unseen_words_count_scores': note_metrics.ideal_unseen_words_count_scores,
                'ideal_word_count': note_metrics.ideal_words_count_scores,
                'words_fr_scores': fields_words_fr_scores_sorted,
                'words_ld_scores': fields_words_ld_scores_sorted
            }
            note['fm_debug_info'] = ''
            for k, var in debug_info.items():
                note['fm_debug_info'] += k+": " + pprint.pformat(var, sort_dicts=False)+"<br />\n"
            update_note = True
        if 'fm_seen_words' in note:
            printed_fields_seen_words = [", ".join(words) for words in note_metrics.seen_words]
            note['fm_seen_words'] = " | ".join(printed_fields_seen_words)
            update_note = True
        if 'fm_unseen_words' in note:
            printed_fields_unseen_words = [", ".join(words) for words in note_metrics.unseen_words]
            note['fm_unseen_words'] = " | ".join(printed_fields_unseen_words)
            update_note = True
        if 'fm_lowest_fr_word' in note:
            printed_fields_lowest_fr_word = [f"{word} ({fr:.2f})" for (word, fr) in note_metrics.lowest_fr_word]
            note['fm_lowest_fr_word'] = " | ".join(printed_fields_lowest_fr_word)
            update_note = True

        if update_note:
            self.modified_dirty_notes.append(note)
