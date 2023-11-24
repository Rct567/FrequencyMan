from dataclasses import dataclass, field
from statistics import fmean
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
    words_fr_scores: dict[WordToken, float] = field(default_factory=dict)
    words_ld_scores: dict[WordToken, float] = field(default_factory=dict)
    words_low_familiarity_scores: dict[WordToken, float] = field(default_factory=dict)
    focus_words: dict[WordToken, float] = field(default_factory=dict)

    seen_words: list[WordToken] = field(default_factory=list)
    unseen_words: list[WordToken] = field(default_factory=list)

    lowest_fr_unseen_word: Tuple[WordToken, float] = (WordToken(""), 0)
    lowest_fr_word: Tuple[WordToken, float] = (WordToken(""), 0)

    highest_ld_word: Tuple[WordToken, float] = (WordToken(""), 0)
    most_obscure_word: Tuple[WordToken, float] = (WordToken(""), 0)

    fr_scores: list[float] = field(default_factory=list)
    ld_scores: list[float] = field(default_factory=list)


@dataclass
class AggregatedFieldsMetrics:
    words_fr_scores: list[dict[WordToken, float]] = field(default_factory=list)
    words_ld_scores: list[dict[WordToken, float]] = field(default_factory=list)
    words_low_familiarity_scores: list[dict[WordToken, float]] = field(default_factory=list)
    focus_words: list[dict[WordToken, float]] = field(default_factory=list)

    seen_words: list[list[WordToken]] = field(default_factory=list)
    unseen_words: list[list[WordToken]] = field(default_factory=list)

    lowest_fr_unseen_word: list[Tuple[WordToken, float]] = field(default_factory=list)
    lowest_fr_word: list[Tuple[WordToken, float]] = field(default_factory=list)

    highest_ld_word: list[Tuple[WordToken, float]] = field(default_factory=list)
    most_obscure_word: list[Tuple[WordToken, float]] = field(default_factory=list)

    fr_scores: list[float] = field(default_factory=list)
    ld_scores: list[float] = field(default_factory=list)

    ideal_unseen_words_count_scores: list[float] = field(default_factory=list)
    ideal_words_count_scores: list[float] = field(default_factory=list)

    def add_field_metrics(self, field_metrics: FieldMetrics):
        self.seen_words.append(field_metrics.seen_words)
        self.unseen_words.append(field_metrics.unseen_words)
        self.lowest_fr_word.append(field_metrics.lowest_fr_word)
        self.lowest_fr_unseen_word.append(field_metrics.lowest_fr_unseen_word)
        self.most_obscure_word.append(field_metrics.most_obscure_word)
        self.highest_ld_word.append(field_metrics.highest_ld_word)
        self.words_fr_scores.append(field_metrics.words_fr_scores)
        self.words_ld_scores.append(field_metrics.words_ld_scores)
        self.words_low_familiarity_scores.append(field_metrics.words_low_familiarity_scores)
        self.focus_words.append(field_metrics.focus_words)


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
        return fmean([max(0, score), 1])

    @staticmethod
    def __calc_ideal_unseen_words_count_score(num_unseen_words: int) -> float:
        if (num_unseen_words < 1):
            return 0.8
        score = min(1, abs(0-(1.6*1/min(num_unseen_words, 10))))
        return score

    def calc_cards_ranking(self, cards: list[Card]) -> dict[CardId, float]:

        notes_from_cards: dict[NoteId, Note] = {}
        cards_per_note: dict[NoteId, list[Card]] = {}  # future use?

        # card ranking is calculates per note (which may have different card, but same ranking)

        for card in cards:
            if card.nid not in notes_from_cards:
                notes_from_cards[card.nid] = self.col.get_note(card.nid)
                if card.nid not in cards_per_note:
                    cards_per_note[card.nid] = []
                cards_per_note[card.nid].append(card)

        # get ranking factors for notes

        notes_ranking_factors, notes_metrics = self.__calc_card_notes_field_metrics(notes_from_cards, cards_per_note)

        # final ranking of cards from notes

        notes_rankings = self.__calc_notes_ranking(notes_ranking_factors)

        # Set meta data that will be saved in note fields
        self.__set_fields_meta_data_for_note(notes_from_cards, notes_ranking_factors, notes_metrics)

        #
        card_rankings: dict[CardId, float] = {}
        for card in cards:
            card_rankings[card.id] = notes_rankings[card.nid]

        return card_rankings

    def __calc_notes_ranking(self, notes_ranking_factors: dict[NoteId, dict[str, float]]) -> dict[NoteId, float]:

        notes_rankings: dict[NoteId, float] = {}

        # get max values

        max_value_per_attribute: dict[str, float] = {}

        for note_id, factors in notes_ranking_factors.items():
            for attribute, value in factors.items():
                if value < 0:
                    raise ValueError("Low value found in ranking factor {}.".format(attribute))
                if attribute not in max_value_per_attribute or value > max_value_per_attribute[attribute]:
                    max_value_per_attribute[attribute] = value

        # normalize

        for note_id, factors in notes_ranking_factors.items():
            for attribute, value in factors.items():
                if max_value_per_attribute[attribute] == 0 or max_value_per_attribute[attribute] == 1:
                    continue
                notes_ranking_factors[note_id][attribute] = notes_ranking_factors[note_id][attribute]/max_value_per_attribute[attribute]

        # final ranking value for notes

        for note_id in notes_ranking_factors.keys():

            note_ranking = fmean(notes_ranking_factors[note_id].values())
            notes_rankings[note_id] = note_ranking

        return notes_rankings

    def __calc_card_notes_field_metrics(self, notes_from_cards: dict[NoteId, Note], cards_per_note: dict[NoteId, list[Card]]) -> Tuple[dict[NoteId, dict[str, float]], dict[NoteId, AggregatedFieldsMetrics]]:

        notes_ranking_factors: dict[NoteId, dict[str, float]] = {}
        notes_metrics: dict[NoteId, AggregatedFieldsMetrics] = {}

        for note_id, note in notes_from_cards.items():

            # get scores per field and assign to note metrics

            note_fields_defined_in_target = self.cards_corpus_data.fields_per_card_note[note.id]
            note_metrics = AggregatedFieldsMetrics()

            for field_data in note_fields_defined_in_target:

                field_key = field_data.field_key

                if not field_key.startswith(str(note.mid)):
                    raise Exception("Card note type id is not matching!?")

                # get metrics for field
                field_metrics = self.__get_field_metrics_from_data(field_data, field_key)

                note_metrics.add_field_metrics(field_metrics)

                # ideal unseen words count
                num_unseen_words = len(field_metrics.unseen_words)
                note_metrics.ideal_unseen_words_count_scores.append(self.__calc_ideal_unseen_words_count_score(num_unseen_words))

                # ideal word count
                note_metrics.ideal_words_count_scores.append(self.__card_field_ideal_word_count_score(len(field_data.field_value_tokenized), 4))

                # fr score
                if (len(field_metrics.fr_scores) > 0):
                    note_metrics.fr_scores.append(fmean(field_metrics.fr_scores))
                else:
                    note_metrics.fr_scores.append(0)

                # ld score
                if (len(field_metrics.ld_scores) > 0):
                    note_metrics.ld_scores.append(fmean(field_metrics.ld_scores))
                else:
                    note_metrics.ld_scores.append(0)

            # define ranking factors for note, based on avg of fields

            note_ranking_factors: dict[str, float] = {}
            note_ranking_factors['words_ld_score'] = fmean(note_metrics.ld_scores)

            note_ranking_factors['highest_ld_word_scores'] = fmean([highest_ld_word[1] for highest_ld_word in note_metrics.highest_ld_word])


            note_ranking_factors['most_obscure_word'] = fmean([most_obscure_word[1] for most_obscure_word in note_metrics.most_obscure_word])

            note_ranking_factors['lowest_fr_unseen_word_scores'] = fmean([lowest_fr_unseen_word[1] for lowest_fr_unseen_word in note_metrics.lowest_fr_unseen_word])

            note_ranking_factors['ideal_unseen_word_count'] = fmean(note_metrics.ideal_unseen_words_count_scores)
            note_ranking_factors['ideal_word_count'] = fmean(note_metrics.ideal_words_count_scores)

            note_ranking_factors['words_low_familiarity_scores'] = fmean([fmean(words_low_familiarity_score.values()) for words_low_familiarity_score in note_metrics.words_low_familiarity_scores])

            # not needed anymore: note_ranking_factors['words_fr_score'] = fmean(note_metrics.fr_scores)

            # todo:
            # card_ranking_factors['words_fresh_occurrence_scores'] = fmean(fields_words_fresh_occurrence_scores)

            notes_ranking_factors[note_id] = note_ranking_factors
            notes_metrics[note_id] = note_metrics

        return notes_ranking_factors, notes_metrics

    def __get_field_metrics_from_data(self, field_data: TargetFieldData, field_key: FieldKey) -> FieldMetrics:

        field_metrics = FieldMetrics()

        for word in field_data.field_value_tokenized:

            word_fr = self.word_frequency_lists.get_word_frequency(field_data.target_language_key, word, 0)
            word_ld = self.cards_corpus_data.get_words_lexical_discrepancy(field_key, word)  # unfamiliarity of high frequency words

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

            #  low familiarity score of words
            word_low_familiarity_score = self.cards_corpus_data.notes_fields_data.reviewed_words_low_familiarity[field_key].get(word, 0)
            field_metrics.words_low_familiarity_scores[word] = word_low_familiarity_score

            # most obscure word (lowest ubiquity)
            word_familiarity_score = self.cards_corpus_data.notes_fields_data.reviewed_words_familiarity[field_key].get(word, 0)
            word_ubiquity_score = (word_fr+word_familiarity_score)/2

            if field_metrics.most_obscure_word[0] == "" or word_ubiquity_score < field_metrics.most_obscure_word[1]:
                field_metrics.most_obscure_word = (word, word_ubiquity_score)

            # focus words
            if word_familiarity_score < self.cards_corpus_data.notes_fields_data.reviewed_words_familiarity_median[field_key]:
                field_metrics.focus_words[word] = word_familiarity_score

            # set seen, unseen and lowest fr unseen
            if word in self.cards_corpus_data.notes_fields_data.reviewed_words[field_key]:
                field_metrics.seen_words.append(word)  # word seen, word exist in at least one reviewed card
            else:
                field_metrics.unseen_words.append(word)
                if field_metrics.lowest_fr_unseen_word[0] == "" or word_fr < field_metrics.lowest_fr_unseen_word[1]:
                    field_metrics.lowest_fr_unseen_word = (word, word_fr)

        return field_metrics

    def __set_fields_meta_data_for_note(self, notes: dict[NoteId, Note], notes_ranking_factors: dict[NoteId, dict[str, float]], notes_metrics: dict[NoteId, AggregatedFieldsMetrics]):

        for note_id, note in notes.items():

            note_metrics = notes_metrics[note_id]

            # set data in card fields
            update_note = False
            if 'fm_debug_info' in note:
                debug_info = {
                    'ld_scores': note_metrics.ld_scores,
                    'fr_scores': note_metrics.fr_scores,
                    'lowest_fr_unseen_word': note_metrics.lowest_fr_unseen_word,
                    'most_obscure_word': note_metrics.most_obscure_word,
                    'highest_ld_word': note_metrics.highest_ld_word,
                    'words_low_familiarity_scores': note_metrics.words_low_familiarity_scores,
                    'ideal_unseen_words_count_scores': note_metrics.ideal_unseen_words_count_scores,
                    'ideal_word_count': note_metrics.ideal_words_count_scores,
                }
                note['fm_debug_info'] = ''
                for info_name, info_val in debug_info.items():
                    fields_info = " | ".join([str(field_info) for field_info in info_val])
                    note['fm_debug_info'] += info_name+": " + fields_info+"<br />\n"
                update_note = True
            if 'fm_debug_words_fr_info' in note:
                fields_words_ld_scores_sorted = [dict(sorted(word_dict.items(), key=lambda item: item[1], reverse=True)) for word_dict in note_metrics.words_ld_scores]
                note['fm_debug_info'] = 'words_ld_scores: '+str(fields_words_ld_scores_sorted)+"\n"
                fields_words_fr_scores_sorted = [dict(sorted(word_dict.items(), key=lambda item: item[1], reverse=True)) for word_dict in note_metrics.words_fr_scores]
                note['fm_debug_words_fr_info'] = 'words_fr_scores: '+str(fields_words_fr_scores_sorted)+"\n"
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
            if 'fm_focus_words' in note:
                focus_words_per_field:list[str] = []
                for focus_words in note_metrics.focus_words:
                    focus_words = dict(sorted(focus_words.items(), key=lambda item: item[1]))
                    focus_words_per_field.append(", ".join([word for (word, familiarity_score) in focus_words.items()]))
                note['fm_focus_words'] = " | ".join(focus_words_per_field)
                update_note = True

            if update_note:
                self.modified_dirty_notes.append(note)
