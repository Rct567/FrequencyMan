from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from math import fsum, exp
from statistics import fmean, median
from typing import Optional, Tuple

from anki.cards import Card, CardId
from anki.notes import Note, NoteId
from anki.collection import Collection

from .target import TargetCardsResult

from .text_processing import WordToken
from .lib.utilities import *
from .target_corpus_data import FieldKey, TargetCorpusData, TargetFieldData
from .word_frequency_list import WordFrequencyLists


def sigmoid(x: float):
    return 1 / (1 + exp(-x))


@dataclass
class FieldMetrics:
    words_fr_scores: dict[WordToken, float] = field(default_factory=dict)
    words_ld_scores: dict[WordToken, float] = field(default_factory=dict)
    words_familiarity_sweetspot_scores: dict[WordToken, float] = field(default_factory=dict)
    words_familiarity_scores: dict[WordToken, float] = field(default_factory=dict)
    focus_words: dict[WordToken, float] = field(default_factory=dict)

    seen_words: list[WordToken] = field(default_factory=list)
    unseen_words: list[WordToken] = field(default_factory=list)

    lowest_fr_least_familiar_word: Tuple[WordToken, float, float] = (WordToken(""), 0, 0)
    lowest_fr_word: Tuple[WordToken, float] = (WordToken(""), 0)

    highest_ld_word: Tuple[WordToken, float] = (WordToken(""), 0)
    most_obscure_word: Tuple[WordToken, float] = (WordToken(""), 0)

    fr_scores: list[float] = field(default_factory=list)
    ld_scores: list[float] = field(default_factory=list)


@dataclass
class AggregatedFieldsMetrics:
    words_fr_scores: list[dict[WordToken, float]] = field(default_factory=list)
    words_ld_scores: list[dict[WordToken, float]] = field(default_factory=list)
    words_familiarity_sweetspot_scores: list[dict[WordToken, float]] = field(default_factory=list)
    words_familiarity_scores: list[dict[WordToken, float]] = field(default_factory=list)
    focus_words: list[dict[WordToken, float]] = field(default_factory=list)

    seen_words: list[list[WordToken]] = field(default_factory=list)
    unseen_words: list[list[WordToken]] = field(default_factory=list)

    lowest_fr_least_familiar_word: list[Tuple[WordToken, float, float]] = field(default_factory=list)
    lowest_fr_word: list[Tuple[WordToken, float]] = field(default_factory=list)

    highest_ld_word: list[Tuple[WordToken, float]] = field(default_factory=list)
    most_obscure_word: list[Tuple[WordToken, float]] = field(default_factory=list)

    fr_scores: list[float] = field(default_factory=list)
    ld_scores: list[float] = field(default_factory=list)
    familiarity_sweetspot_scores: list[float] = field(default_factory=list)
    familiarity_scores: list[float] = field(default_factory=list)

    ideal_unseen_words_count_scores: list[float] = field(default_factory=list)
    ideal_words_count_scores: list[float] = field(default_factory=list)
    ideal_focus_words_count_scores: list[float] = field(default_factory=list)

    def append_field_metrics(self, field_metrics: FieldMetrics):
        self.seen_words.append(field_metrics.seen_words)
        self.unseen_words.append(field_metrics.unseen_words)
        self.lowest_fr_word.append(field_metrics.lowest_fr_word)
        self.lowest_fr_least_familiar_word.append(field_metrics.lowest_fr_least_familiar_word)
        self.most_obscure_word.append(field_metrics.most_obscure_word)
        self.highest_ld_word.append(field_metrics.highest_ld_word)
        self.words_fr_scores.append(field_metrics.words_fr_scores)
        self.words_ld_scores.append(field_metrics.words_ld_scores)
        self.words_familiarity_sweetspot_scores.append(field_metrics.words_familiarity_sweetspot_scores)
        self.words_familiarity_scores.append(field_metrics.words_familiarity_scores)
        self.focus_words.append(field_metrics.focus_words)


class CardRanker:

    modified_dirty_notes: dict[NoteId, Note]
    ranking_factors_span: dict[str, float]
    ranking_factors_stats: Optional[dict[str, dict[str, float]]]

    def __init__(self, cards_corpus_data: TargetCorpusData, word_frequency_lists: WordFrequencyLists, col: Collection) -> None:

        self.cards_corpus_data = cards_corpus_data
        self.word_frequency_lists = word_frequency_lists
        self.col = col
        self.modified_dirty_notes = {}
        self.ranking_factors_stats = None

        self.ranking_factors_span = {
            'words_fr_score': 0.25,
            'lowest_fr_word_score': 0.25,
            'words_ld_score': 0.25,
            'highest_ld_word_score': 0.25,
            'most_obscure_word': 1.0,
            'ideal_word_count': 1.0,
            'ideal_focus_word_count': 1.5,
            'words_familiarity_scores': 0.0,
            'words_familiarity_sweetspot_scores': 1.0,
            'lowest_fr_least_familiar_word_scores': 1.0,
            'ideal_unseen_word_count': 0.1,
        }

    @staticmethod
    def __card_field_ideal_word_count_score(word_count: int, ideal_num_min: int, ideal_num_max: int) -> float:
        if word_count >= ideal_num_min and word_count <= ideal_num_max:
            return 1
        middle = (ideal_num_min+ideal_num_max)/2
        difference = abs(middle-word_count)
        score = 1 / (1 + (difference / middle) ** 7)
        if (word_count > 0 and word_count < ideal_num_min):
            return fmean([score, 1])
        return score

    @staticmethod
    def __calc_ideal_unseen_words_count_score(num_unseen_words: int) -> float:
        if (num_unseen_words < 1):
            return 0.9
        score = min(1, abs(0-(1.4*1/min(num_unseen_words, 10))))
        return score

    def calc_cards_ranking(self, target_cards: TargetCardsResult) -> dict[CardId, float]:

        notes_from_new_cards: dict[NoteId, Note] = {}

        # card ranking is calculates per note (which may have different card, but same ranking)

        for card in target_cards.new_cards:
            if card.nid not in notes_from_new_cards:
                notes_from_new_cards[card.nid] = self.col.get_note(card.nid)

        # get ranking factors for notes

        notes_ranking_factors, notes_metrics = self.__calc_card_notes_field_metrics(notes_from_new_cards)

        # final ranking of cards from notes

        notes_ranking_factors_normalized, notes_rankings = self.__calc_notes_ranking(notes_ranking_factors)

        # Set meta data that will be saved in note fields
        self.__set_fields_meta_data_for_note(notes_from_new_cards, notes_ranking_factors_normalized, notes_metrics)
        self.__update_meta_data_for_notes_with_non_new_cards(target_cards)  # reviewed card also need updating

        #
        card_rankings: dict[CardId, float] = {}
        for card in target_cards.new_cards:
            card_rankings[card.id] = notes_rankings[card.nid]

        return card_rankings

    def __calc_notes_ranking(self, notes_ranking_factors: dict[NoteId, dict[str, float]]) -> tuple[dict[NoteId, dict[str, float]], dict[NoteId, float]]:

        notes_ranking_factors_normalized = deepcopy(notes_ranking_factors)
        useable_factors: set[str] = set()

        # perform Z-score standardization, use sigmoid and then 0 to 1 normalization

        for attribute in self.ranking_factors_span.keys():

            values = [note[attribute] for note in notes_ranking_factors_normalized.values()]
            mean_val = fmean(values)
            std_dev = (fsum((x - mean_val) ** 2 for x in values) / len(values)) ** 0.5

            if (min(values) < 0):
                raise ValueError("Low value found in ranking factor {}.".format(attribute))
            if not std_dev > 0:
                continue

            for note_id, factors in notes_ranking_factors_normalized.items():
                notes_ranking_factors_normalized[note_id][attribute] = (notes_ranking_factors_normalized[note_id][attribute] - mean_val) / std_dev
                notes_ranking_factors_normalized[note_id][attribute] = sigmoid(notes_ranking_factors_normalized[note_id][attribute])

            lowest = min([note[attribute] for note in notes_ranking_factors_normalized.values()])

            if lowest < 0:
                for note_id, factors in notes_ranking_factors_normalized.items():
                    notes_ranking_factors_normalized[note_id][attribute] = abs(lowest)+notes_ranking_factors_normalized[note_id][attribute]

            highest = max([note[attribute] for note in notes_ranking_factors_normalized.values()])

            if highest > 0:
                for note_id, factors in notes_ranking_factors_normalized.items():
                    notes_ranking_factors_normalized[note_id][attribute] = notes_ranking_factors_normalized[note_id][attribute]/highest
                useable_factors.add(attribute)

        # set stats

        self.ranking_factors_stats = defaultdict(dict)
        for attribute in self.ranking_factors_span.keys():
            vals = [note[attribute] for note in notes_ranking_factors_normalized.values()]
            self.ranking_factors_stats[attribute]['avg'] = fmean(vals)
            self.ranking_factors_stats[attribute]['median'] = median(vals)

        # ranking factors span

        notes_spanned_ranking_factors: dict[NoteId, dict[str, float]] = defaultdict(dict)

        for note_id, factors in notes_ranking_factors_normalized.items():
            for attribute, value in factors.items():
                if attribute not in self.ranking_factors_span:
                    raise Exception("Unknown span for ranking factor {}".format(attribute))
                if not attribute in useable_factors:
                    continue
                if self.ranking_factors_span[attribute] == 0:
                    continue
                notes_spanned_ranking_factors[note_id][attribute] = value * float(self.ranking_factors_span[attribute])

        # final ranking value for notes

        notes_rankings: dict[NoteId, float] = {}

        for note_id in notes_ranking_factors_normalized.keys():
            total_value = fsum(notes_spanned_ranking_factors[note_id].values())
            span = fsum(self.ranking_factors_span.values())
            notes_rankings[note_id] = total_value/span

        return notes_ranking_factors_normalized, notes_rankings

    def __calc_card_notes_field_metrics(self, notes_from_new_cards: dict[NoteId, Note]) -> Tuple[dict[NoteId, dict[str, float]], dict[NoteId, AggregatedFieldsMetrics]]:

        notes_ranking_factors: dict[NoteId, dict[str, float]] = {}
        notes_metrics: dict[NoteId, AggregatedFieldsMetrics] = {}

        for note_id, note in notes_from_new_cards.items():

            # get scores per field and assign to note metrics

            note_fields_defined_in_target = self.cards_corpus_data.fields_per_card_note[note.id]
            note_metrics = AggregatedFieldsMetrics()

            for field_data in note_fields_defined_in_target:

                field_key = field_data.field_key

                if not field_key.startswith(str(note.mid)):
                    raise Exception("Card note type id is not matching!?")

                # get metrics for field
                field_metrics = self.__get_field_metrics_from_data(field_data, field_key)

                # append existing field metrics (additional metrics created and added below)
                note_metrics.append_field_metrics(field_metrics)

                # ideal unseen words count
                num_unseen_words = len(field_metrics.unseen_words)
                note_metrics.ideal_unseen_words_count_scores.append(self.__calc_ideal_unseen_words_count_score(num_unseen_words))

                # ideal focus words count
                num_focus_words = len(field_metrics.focus_words)
                note_metrics.ideal_focus_words_count_scores.append(self.__calc_ideal_unseen_words_count_score(num_focus_words))

                # ideal word count
                note_metrics.ideal_words_count_scores.append(self.__card_field_ideal_word_count_score(len(field_data.field_value_tokenized), 2, 5))

                # familiarity scores
                if len(field_metrics.words_familiarity_scores) > 0:
                    note_metrics.familiarity_scores.append(fmean(field_metrics.words_familiarity_scores.values()))
                else:
                    note_metrics.familiarity_scores.append(0)

                # familiarity sweetspot scores
                if len(field_metrics.words_familiarity_sweetspot_scores) > 0:
                    note_metrics.familiarity_sweetspot_scores.append(fsum(field_metrics.words_familiarity_sweetspot_scores.values()))
                else:
                    note_metrics.familiarity_sweetspot_scores.append(0)

                # fr scores
                if (len(field_metrics.fr_scores) > 0):
                    note_metrics.fr_scores.append(fmean(field_metrics.fr_scores))
                else:
                    note_metrics.fr_scores.append(0)

                # ld scores
                if (len(field_metrics.ld_scores) > 0):
                    note_metrics.ld_scores.append(fsum(field_metrics.ld_scores))
                else:
                    note_metrics.ld_scores.append(0)

            # define ranking factors for note, based on avg of fields

            note_ranking_factors: dict[str, float] = {}

            note_ranking_factors['words_fr_score'] = fmean(note_metrics.fr_scores)
            note_ranking_factors['words_ld_score'] = fmean(note_metrics.ld_scores)

            note_ranking_factors['lowest_fr_word_score'] = fmean([lowest_fr_word[1] for lowest_fr_word in note_metrics.lowest_fr_word])
            note_ranking_factors['highest_ld_word_score'] = fmean([highest_ld_word[1] for highest_ld_word in note_metrics.highest_ld_word])

            note_ranking_factors['most_obscure_word'] = fmean([most_obscure_word[1] for most_obscure_word in note_metrics.most_obscure_word])

            note_ranking_factors['ideal_word_count'] = fmean(note_metrics.ideal_words_count_scores)
            note_ranking_factors['ideal_focus_word_count'] = fmean(note_metrics.ideal_focus_words_count_scores)

            note_ranking_factors['words_familiarity_scores'] = fmean(note_metrics.familiarity_scores)
            note_ranking_factors['words_familiarity_sweetspot_scores'] = fmean(note_metrics.familiarity_sweetspot_scores)

            note_ranking_factors['lowest_fr_least_familiar_word_scores'] = fmean([lowest_fr_unseen_word[1] for lowest_fr_unseen_word in note_metrics.lowest_fr_least_familiar_word])
            note_ranking_factors['ideal_unseen_word_count'] = fmean(note_metrics.ideal_unseen_words_count_scores)

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

            #  familiarity score of words
            word_familiarity_score = self.cards_corpus_data.notes_fields_data.reviewed_words_familiarity[field_key].get(word, 0)
            field_metrics.words_familiarity_scores[word] = word_familiarity_score

            # familiarity sweetspot score of words in sweetspot range
            word_familiarity_sweetspot_score = self.cards_corpus_data.notes_fields_data.reviewed_words_familiarity_sweetspot[field_key].get(word, None)
            if word_familiarity_sweetspot_score is not None:
                field_metrics.words_familiarity_sweetspot_scores[word] = word_familiarity_sweetspot_score

            # most obscure word (lowest ubiquity)
            word_familiarity_score = self.cards_corpus_data.notes_fields_data.reviewed_words_familiarity[field_key].get(word, 0)
            word_ubiquity_score = (word_fr+word_familiarity_score)/2

            if field_metrics.most_obscure_word[0] == "" or word_ubiquity_score < field_metrics.most_obscure_word[1]:
                field_metrics.most_obscure_word = (word, word_ubiquity_score)

            # focus words
            if word_familiarity_score < (0.9*self.cards_corpus_data.notes_fields_data.reviewed_words_familiarity_median[field_key]):
                field_metrics.focus_words[word] = word_familiarity_score

            # set seen and unseen
            if word in self.cards_corpus_data.notes_fields_data.reviewed_words[field_key]:
                field_metrics.seen_words.append(word)  # word seen, word exist in at least one reviewed card
            else:
                field_metrics.unseen_words.append(word)

            # set lowest fr of least familiar word
            if field_metrics.lowest_fr_least_familiar_word[0] == "" or word_familiarity_score < field_metrics.lowest_fr_least_familiar_word[2]:
                field_metrics.lowest_fr_least_familiar_word = (word, word_fr, word_familiarity_score)
            elif word_familiarity_score == field_metrics.lowest_fr_least_familiar_word[2]:
                if word_fr < field_metrics.lowest_fr_least_familiar_word[1]:
                    field_metrics.lowest_fr_least_familiar_word = (word, word_fr, word_familiarity_score)

        return field_metrics

    def __set_fields_meta_data_for_note(self, notes_from_new_cards: dict[NoteId, Note], notes_ranking_factors: dict[NoteId, dict[str, float]], notes_metrics: dict[NoteId, AggregatedFieldsMetrics]):

        for note_id, note in notes_from_new_cards.items():

            note_metrics = notes_metrics[note_id]

            # set data in card fields
            update_note = False
            if 'fm_debug_info' in note:
                debug_info = {
                    'fr_scores': note_metrics.fr_scores,
                    'ld_scores': note_metrics.ld_scores,
                    'most_obscure_word': note_metrics.most_obscure_word,
                    'highest_ld_word': note_metrics.highest_ld_word,
                    'ideal_focus_word_count': note_metrics.ideal_focus_words_count_scores,
                    'ideal_word_count': note_metrics.ideal_words_count_scores,
                    'familiarity_scores': note_metrics.familiarity_scores,
                    'familiarity_sweetspot_scores': note_metrics.familiarity_sweetspot_scores,
                    'lowest_fr_least_familiar_word': note_metrics.lowest_fr_least_familiar_word,
                    'lowest_fr_word': note_metrics.lowest_fr_word,
                    'ideal_unseen_words_count_scores': note_metrics.ideal_unseen_words_count_scores,
                }
                note['fm_debug_info'] = ''
                for info_name, info_val in debug_info.items():
                    fields_info = " | ".join([str(field_info) for field_info in info_val]).strip("| ")
                    note['fm_debug_info'] += info_name+": " + fields_info+"<br />\n"
                update_note = True
            if 'fm_debug_ranking_info' in note:
                note['fm_debug_ranking_info'] = ''
                for info_name, info_val in notes_ranking_factors[note_id].items():
                    note['fm_debug_ranking_info'] += f"{info_name}: {info_val:.3f}<br />\n"
                update_note = True
            if 'fm_debug_words_info' in note:
                note['fm_debug_words_info'] = ''
                fields_words_ld_scores_sorted = [dict(sorted(word_dict.items(), key=lambda item: item[1], reverse=True)) for word_dict in note_metrics.words_ld_scores]
                note['fm_debug_words_info'] += 'words_ld_scores: '+str(fields_words_ld_scores_sorted)+"<br />\n"
                fields_words_fr_scores_sorted = [dict(sorted(word_dict.items(), key=lambda item: item[1], reverse=True)) for word_dict in note_metrics.words_fr_scores]
                note['fm_debug_words_info'] += 'words_fr_scores: '+str(fields_words_fr_scores_sorted)+"<br />\n"
                fields_words_familiarity_sweetspot_scores_sorted = [dict(sorted(word_dict.items(), key=lambda item: item[1], reverse=True))
                                                                    for word_dict in note_metrics.words_familiarity_sweetspot_scores]
                note['fm_debug_words_info'] += 'familiarity_sweetspot_scores: '+str(fields_words_familiarity_sweetspot_scores_sorted)+"<br />\n"
                fields_words_familiarity_scores_sorted = [dict(sorted(word_dict.items(), key=lambda item: item[1], reverse=True)) for word_dict in note_metrics.words_familiarity_scores]
                note['fm_debug_words_info'] += 'familiarity_scores: '+str(fields_words_familiarity_scores_sorted)+"<br />\n"
                update_note = True
            if 'fm_seen_words' in note:
                printed_fields_seen_words = [", ".join(words).strip(", ") for words in note_metrics.seen_words]
                note['fm_seen_words'] = " | ".join(printed_fields_seen_words).strip("| ")
                update_note = True
            if 'fm_unseen_words' in note:
                printed_fields_unseen_words = [", ".join(words) for words in note_metrics.unseen_words]
                note['fm_unseen_words'] = " | ".join(printed_fields_unseen_words).strip("| ")
                update_note = True
            if 'fm_focus_words' in note:
                focus_words_per_field: list[str] = []
                for focus_words in note_metrics.focus_words:
                    focus_words = dict(sorted(focus_words.items(), key=lambda item: item[1]))
                    focus_words_per_field.append(", ".join([word for word in focus_words.keys()]))
                note['fm_focus_words'] = " | ".join(focus_words_per_field).strip("| ")
                update_note = True

            if update_note:
                self.modified_dirty_notes[note_id] = note

    def __get_note_focus_word(self, note_id: NoteId) -> AggregatedFieldsMetrics:

        note_fields_defined_in_target = self.cards_corpus_data.fields_per_card_note[note_id]
        note_metrics = AggregatedFieldsMetrics()

        for field_data in note_fields_defined_in_target:
            field_metrics = self.__get_field_metrics_from_data(field_data, field_data.field_key)
            note_metrics.append_field_metrics(field_metrics)

        return note_metrics

    def __update_meta_data_for_notes_with_non_new_cards(self, target_cards: TargetCardsResult) -> None:

        for note_id, note in target_cards.get_notes().items():
            if not note_id in self.modified_dirty_notes:
                update_note = False
                field_to_clear = ['fm_debug_info', 'fm_debug_ranking_info', 'fm_debug_words_info', 'fm_seen_words', 'fm_unseen_words']
                for field_name in field_to_clear:
                    if field_name in note and note[field_name] != '':
                        note[field_name] = ''
                        update_note = True

                if 'fm_focus_words' in note:
                    focus_words_per_field: list[str] = []
                    for focus_words in self.__get_note_focus_word(note_id).focus_words:
                        focus_words = dict(sorted(focus_words.items(), key=lambda item: item[1]))
                        focus_words_per_field.append(", ".join([word for word in focus_words.keys()]))
                    note['fm_focus_words'] = " | ".join(focus_words_per_field).strip("| ")
                    update_note = True

                if update_note:
                    self.modified_dirty_notes[note_id] = note
