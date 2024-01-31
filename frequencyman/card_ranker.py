"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from math import fsum, exp
from statistics import fmean, median
from typing import Optional, Tuple

from anki.cards import Card, CardId
from anki.notes import Note, NoteId
from anki.collection import Collection

from .target import TargetCards

from .text_processing import WordToken
from .lib.utilities import *
from .target_corpus_data import CorpusId, TargetCorpusData, TargetNoteFieldContentData
from .language_data import LanguageData


def sigmoid(x: float):
    return 1 / (1 + exp(-x))


@dataclass
class FieldMetrics:
    words_fr_scores: dict[WordToken, float] = field(default_factory=dict)
    words_ue_scores: dict[WordToken, float] = field(default_factory=dict)
    words_familiarity_sweetspot_scores: dict[WordToken, float] = field(default_factory=dict)
    words_familiarity_scores: dict[WordToken, float] = field(default_factory=dict)
    words_familiarity_positional_scores: dict[WordToken, float] = field(default_factory=dict)
    focus_words: dict[WordToken, float] = field(default_factory=dict)

    seen_words: list[WordToken] = field(default_factory=list)
    unseen_words: list[WordToken] = field(default_factory=list)

    lowest_fr_least_familiar_word: Tuple[WordToken, float, float] = (WordToken(""), 0, 0)
    lowest_fr_word: Tuple[WordToken, float] = (WordToken(""), 0)

    highest_ue_word: Tuple[WordToken, float] = (WordToken(""), 0)
    most_obscure_word: Tuple[WordToken, float] = (WordToken(""), 0)

    fr_scores: list[float] = field(default_factory=list)
    ue_scores: list[float] = field(default_factory=list)


@dataclass
class AggregatedFieldsMetrics:
    words_fr_scores: list[dict[WordToken, float]] = field(default_factory=list)
    words_ue_scores: list[dict[WordToken, float]] = field(default_factory=list)
    words_familiarity_sweetspot_scores: list[dict[WordToken, float]] = field(default_factory=list)
    words_familiarity_scores: list[dict[WordToken, float]] = field(default_factory=list)
    focus_words: list[dict[WordToken, float]] = field(default_factory=list)

    seen_words: list[list[WordToken]] = field(default_factory=list)
    unseen_words: list[list[WordToken]] = field(default_factory=list)

    lowest_fr_least_familiar_word: list[Tuple[WordToken, float, float]] = field(default_factory=list)
    lowest_fr_word: list[Tuple[WordToken, float]] = field(default_factory=list)

    highest_ue_word: list[Tuple[WordToken, float]] = field(default_factory=list)
    most_obscure_word: list[Tuple[WordToken, float]] = field(default_factory=list)

    fr_scores: list[float] = field(default_factory=list)
    ue_scores: list[float] = field(default_factory=list)
    familiarity_sweetspot_scores: list[float] = field(default_factory=list)
    familiarity_scores: list[float] = field(default_factory=list)

    ideal_unseen_words_count_scores: list[float] = field(default_factory=list)
    ideal_words_count_scores: list[float] = field(default_factory=list)
    ideal_focus_words_count_scores: list[float] = field(default_factory=list)


class CardRanker:

    modified_dirty_notes: dict[NoteId, Optional[Note]]
    ranking_factors_span: dict[str, float]
    ranking_factors_stats: Optional[dict[str, dict[str, float]]]
    ideal_word_count_min: int
    ideal_word_count_max: int

    def __init__(self, target_corpus_data: TargetCorpusData, language_data: LanguageData,
                 col: Collection, modified_dirty_notes: dict[NoteId, Optional[Note]]) -> None:

        self.corpus_data = target_corpus_data
        self.language_data = language_data
        self.col = col
        self.modified_dirty_notes = modified_dirty_notes
        self.ranking_factors_stats = None
        self.ranking_factors_span = self.get_default_ranking_factors_span()
        self.ideal_word_count_min = 2
        self.ideal_word_count_max = 5

    @staticmethod
    def get_default_ranking_factors_span() -> dict[str, float]:
        return {
            'word_frequency': 1,
            'familiarity': 1,
            'familiarity_sweetspot': 0.5,
            'lexical_underexposure': 0.4,
            'ideal_focus_word_count': 1.5,
            'ideal_word_count': 1.0,
            'most_obscure_word': 1.0,
            'lowest_fr_least_familiar_word': 1.0,
            'ideal_unseen_word_count': 0,
            'word_frequency_lowest': 0,
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

    def calc_cards_ranking(self, target_cards: TargetCards) -> dict[CardId, float]:

        # card ranking is calculates per note (which may have different card, but same ranking)

        notes_from_new_cards = target_cards.get_notes_from_new_cards()

        # get ranking factors for notes

        notes_metrics = self.__calc_card_notes_field_metrics(notes_from_new_cards, with_additional_props=True)
        notes_ranking_factors = self.__get_notes_ranking_factors(notes_metrics)

        # final ranking of cards from notes

        notes_ranking_scores_normalized, notes_rankings = self.__calc_notes_ranking(notes_ranking_factors)

        # Set meta data that will be saved in note fields
        self.__set_fields_meta_data_for_notes(notes_from_new_cards, notes_ranking_scores_normalized, notes_metrics)
        self.__update_meta_data_for_notes_with_non_new_cards(target_cards)  # reviewed card also need updating

        #
        card_rankings: dict[CardId, float] = {}
        for card in target_cards.new_cards:
            card_rankings[card.id] = notes_rankings[card.nid]

        return card_rankings

    def __calc_notes_ranking(self, notes_ranking_scores: dict[str, dict[NoteId, float]]) -> tuple[dict[str, dict[NoteId, float]], dict[NoteId, float]]:

        notes_ranking_scores_normalized = notes_ranking_scores.copy()

        useable_factors: set[str] = set()

        # perform Z-score standardization, use sigmoid and then 0 to 1 normalization

        for attribute, notes_scores in notes_ranking_scores_normalized.items():

            values = notes_scores.values()
            mean_val = fmean(values)
            std_dev = (fsum((x - mean_val) ** 2 for x in values) / len(values)) ** 0.5

            if min(values) < 0:
                raise ValueError("Below zero value found in ranking factor {}.".format(attribute))
            if not std_dev > 0:
                continue

            lowest_val = 0.0

            for note_id in notes_scores.keys():
                notes_scores[note_id] = (notes_scores[note_id] - mean_val) / std_dev
                notes_scores[note_id] = sigmoid(notes_scores[note_id])
                if lowest_val > notes_scores[note_id]:
                    lowest_val = notes_scores[note_id]

            if lowest_val < 0:
                for note_id in notes_scores.keys():
                    notes_scores[note_id] = abs(lowest_val)+notes_scores[note_id]

            highest_val = max(notes_scores.values())

            if highest_val > 0:
                for note_id in notes_scores.keys():
                    notes_scores[note_id] = notes_scores[note_id]/highest_val
                useable_factors.add(attribute)

            notes_ranking_scores_normalized[attribute] = notes_scores

        # set stats

        self.ranking_factors_stats = defaultdict(dict)
        for attribute in self.ranking_factors_span.keys():
            if attribute not in notes_ranking_scores_normalized:
                raise Exception("Span set for unknown ranking factor '{}'.".format(attribute))
            vals = notes_ranking_scores_normalized[attribute]
            self.ranking_factors_stats[attribute]['avg'] = fmean(vals)
            self.ranking_factors_stats[attribute]['median'] = median(vals)

        # ranking factors span

        notes_spanned_ranking_factors: dict[NoteId, dict[str, float]] = defaultdict(dict)

        for attribute, notes_scores in notes_ranking_scores_normalized.items():
            if attribute not in self.ranking_factors_span or self.ranking_factors_span[attribute] == 0:
                continue
            if not attribute in useable_factors:
                continue
            for note_id, value in notes_scores.items():
                notes_spanned_ranking_factors[note_id][attribute] = value * float(self.ranking_factors_span[attribute])

        # final ranking value for notes

        notes_rankings: dict[NoteId, float] = {}

        for note_id in notes_spanned_ranking_factors.keys():
            total_value = fsum(notes_spanned_ranking_factors[note_id].values())
            span = fsum(self.ranking_factors_span.values())
            notes_rankings[note_id] = total_value/span

        return notes_ranking_scores_normalized, notes_rankings

    def __calc_card_notes_field_metrics(self, notes_from_new_cards: dict[NoteId, Note], with_additional_props: bool) -> dict[NoteId, AggregatedFieldsMetrics]:

        notes_metrics: dict[NoteId, AggregatedFieldsMetrics] = {note_id: AggregatedFieldsMetrics() for note_id in notes_from_new_cards.keys()}

        for note_id, note in notes_from_new_cards.items():

            # get scores per note field and append to note metrics

            note_fields_defined_in_target = self.corpus_data.field_data_per_card_note[note.id]
            note_metrics = notes_metrics[note_id]

            for field_data in note_fields_defined_in_target:

                if not field_data.corpus_id.startswith(str(note.mid)):
                    raise Exception("Card note type id is not matching!?")

                # get metrics for field
                field_metrics = self.__get_field_metrics_from_data(field_data, field_data.corpus_id)

                # append existing field metrics (additional metrics created and added below)
                note_metrics.seen_words.append(field_metrics.seen_words)
                note_metrics.unseen_words.append(field_metrics.unseen_words)
                note_metrics.lowest_fr_word.append(field_metrics.lowest_fr_word)
                note_metrics.lowest_fr_least_familiar_word.append(field_metrics.lowest_fr_least_familiar_word)
                note_metrics.most_obscure_word.append(field_metrics.most_obscure_word)
                note_metrics.highest_ue_word.append(field_metrics.highest_ue_word)
                note_metrics.words_fr_scores.append(field_metrics.words_fr_scores)
                note_metrics.words_ue_scores.append(field_metrics.words_ue_scores)
                note_metrics.words_familiarity_sweetspot_scores.append(field_metrics.words_familiarity_sweetspot_scores)
                note_metrics.words_familiarity_scores.append(field_metrics.words_familiarity_scores)
                note_metrics.focus_words.append(field_metrics.focus_words)

                # skip the rest if needed
                if not with_additional_props:
                    continue

                # ideal unseen words count
                field_num_unseen_words_score = self.__calc_ideal_unseen_words_count_score(len(field_metrics.unseen_words))
                note_metrics.ideal_unseen_words_count_scores.append(field_num_unseen_words_score)

                # ideal focus words count
                field_num_focus_words_score = self.__calc_ideal_unseen_words_count_score(len(field_metrics.focus_words))
                note_metrics.ideal_focus_words_count_scores.append(field_num_focus_words_score)

                # ideal word count
                field_ideal_word_count_score = self.__card_field_ideal_word_count_score(len(field_data.field_value_tokenized), self.ideal_word_count_min, self.ideal_word_count_max)
                note_metrics.ideal_words_count_scores.append(field_ideal_word_count_score)

                # familiarity scores (push down)
                if len(field_metrics.words_familiarity_positional_scores) > 0:
                    words_familiarity_positional_scores = field_metrics.words_familiarity_positional_scores.values()
                    field_familiarity_score = fmean([median(words_familiarity_positional_scores), min(words_familiarity_positional_scores)])
                    note_metrics.familiarity_scores.append(field_familiarity_score)
                else:
                    note_metrics.familiarity_scores.append(0)

                # familiarity sweetspot scores (push up)
                if len(field_metrics.words_familiarity_sweetspot_scores) > 0:
                    words_familiarity_sweetspot_scores = field_metrics.words_familiarity_sweetspot_scores.values()
                    field_familiarity_sweetspot_score = fmean([fmean(words_familiarity_sweetspot_scores), max(words_familiarity_sweetspot_scores)])
                    note_metrics.familiarity_sweetspot_scores.append(field_familiarity_sweetspot_score)
                else:
                    note_metrics.familiarity_sweetspot_scores.append(0)

                # word frequency scores (push down)
                if (len(field_metrics.fr_scores) > 0):
                    field_fr_score = fmean([median(field_metrics.fr_scores), min(field_metrics.fr_scores)])
                    note_metrics.fr_scores.append(field_fr_score)
                else:
                    note_metrics.fr_scores.append(0)

                # underexposure scores (push up)
                if (len(field_metrics.ue_scores) > 0):
                    field_ue_score = fmean([fmean(field_metrics.ue_scores), max(field_metrics.ue_scores)])
                    note_metrics.ue_scores.append(field_ue_score)
                else:
                    note_metrics.ue_scores.append(0)

        return notes_metrics

    def __get_field_metrics_from_data(self, field_data: TargetNoteFieldContentData, corpus_key: CorpusId) -> FieldMetrics:

        field_metrics = FieldMetrics()
        content_metrics = self.corpus_data.content_metrics[corpus_key]

        for word in field_data.field_value_tokenized:

            # skip if word is in ignore list
            if self.language_data.is_ignore_word(field_data.target_language_data_id, word):
                continue

            # word frequency
            word_fr = self.language_data.get_word_frequency(field_data.target_language_data_id, word, 0)
            word_ue = content_metrics.words_underexposure.get(word, 0)

            field_metrics.fr_scores.append(word_fr)
            field_metrics.words_fr_scores[word] = word_fr

            field_metrics.ue_scores.append(word_ue)
            field_metrics.words_ue_scores[word] = word_ue

            # lowest fr word
            if field_metrics.lowest_fr_word[0] == "" or word_fr < field_metrics.lowest_fr_word[1]:
                field_metrics.lowest_fr_word = (word, word_fr)

            # most underexposure word
            if field_metrics.highest_ue_word[0] == "" or word_ue > field_metrics.highest_ue_word[1]:
                field_metrics.highest_ue_word = (word, word_ue)

            #  familiarity score of words
            word_familiarity_score = content_metrics.reviewed.words_familiarity.get(word, 0)
            field_metrics.words_familiarity_scores[word] = word_familiarity_score

            words_familiarity_positional = content_metrics.reviewed.words_familiarity_positional.get(word, 0)
            field_metrics.words_familiarity_positional_scores[word] = words_familiarity_positional

            # familiarity sweetspot score of words in sweetspot range
            word_familiarity_sweetspot_score = content_metrics.reviewed.words_familiarity_sweetspot.get(word, 0)
            if word_familiarity_sweetspot_score > 0:
                field_metrics.words_familiarity_sweetspot_scores[word] = word_familiarity_sweetspot_score

            # most obscure word (lowest ubiquity)
            word_ubiquity_score = (word_fr+word_familiarity_score)/2
            if field_metrics.most_obscure_word[0] == "" or word_ubiquity_score < field_metrics.most_obscure_word[1]:
                field_metrics.most_obscure_word = (word, word_ubiquity_score)

            # focus words
            if word_familiarity_score < (0.9*content_metrics.reviewed.words_familiarity_median):
                field_metrics.focus_words[word] = word_familiarity_score

            # set seen and unseen
            if word in content_metrics.reviewed.words:
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

    def __get_notes_ranking_factors(self, notes_metrics: dict[NoteId, AggregatedFieldsMetrics]) -> dict[str, dict[NoteId, float]]:

        notes_ranking_factors: dict[str, dict[NoteId, float]] = defaultdict(dict)

        for note_id in notes_metrics.keys():

            note_metrics = notes_metrics[note_id]

            # define ranking factors for note, based on avg of fields

            notes_ranking_factors['word_frequency'][note_id] = fmean(note_metrics.fr_scores)
            notes_ranking_factors['word_frequency_lowest'][note_id] = fmean([lowest_fr_word[1] for lowest_fr_word in note_metrics.lowest_fr_word])

            notes_ranking_factors['lexical_underexposure'][note_id] = fmean(note_metrics.ue_scores)

            notes_ranking_factors['most_obscure_word'][note_id] = fmean([most_obscure_word[1] for most_obscure_word in note_metrics.most_obscure_word])

            notes_ranking_factors['ideal_word_count'][note_id] = fmean(note_metrics.ideal_words_count_scores)
            notes_ranking_factors['ideal_focus_word_count'][note_id] = fmean(note_metrics.ideal_focus_words_count_scores)

            notes_ranking_factors['familiarity'][note_id] = fmean(note_metrics.familiarity_scores)
            notes_ranking_factors['familiarity_sweetspot'][note_id] = fmean(note_metrics.familiarity_sweetspot_scores)

            notes_ranking_factors['lowest_fr_least_familiar_word'][note_id] = fmean([lowest_fr_unseen_word[1] for lowest_fr_unseen_word in note_metrics.lowest_fr_least_familiar_word])
            notes_ranking_factors['ideal_unseen_word_count'][note_id] = fmean(note_metrics.ideal_unseen_words_count_scores)

        return notes_ranking_factors

    def __set_fields_meta_data_for_notes(self, notes_from_new_cards: dict[NoteId, Note], notes_ranking_scores: dict[str, dict[NoteId, float]], notes_metrics: dict[NoteId, AggregatedFieldsMetrics]):

        for note_id, note in notes_from_new_cards.items():

            if note_id in self.modified_dirty_notes:
                continue

            note_metrics = notes_metrics[note_id]
            new_note_vals: dict[str, str] = {}

            if 'fm_debug_info' in note:
                debug_info: dict[str, list] = {
                    'fr_scores': note_metrics.fr_scores,
                    'ue_scores': note_metrics.ue_scores,
                    'most_obscure_word': note_metrics.most_obscure_word,
                    'highest_ue_word': note_metrics.highest_ue_word,
                    'ideal_focus_word_count': note_metrics.ideal_focus_words_count_scores,
                    'ideal_word_count': note_metrics.ideal_words_count_scores,
                    'familiarity_scores': note_metrics.familiarity_scores,
                    'familiarity_sweetspot_scores': note_metrics.familiarity_sweetspot_scores,
                    'lowest_fr_least_familiar_word': note_metrics.lowest_fr_least_familiar_word,
                    'lowest_fr_word': note_metrics.lowest_fr_word,
                    'ideal_unseen_words_count_scores': note_metrics.ideal_unseen_words_count_scores,
                }
                new_note_vals['fm_debug_info'] = ''
                for info_name, info_val in debug_info.items():
                    fields_info = " | ".join([str(field_info) for field_info in info_val]).strip("| ")
                    new_note_vals['fm_debug_info'] += info_name+": " + fields_info+"<br />\n"
            if 'fm_debug_ranking_info' in note:
                new_note_vals['fm_debug_ranking_info'] = ''
                for info_name, info_val in notes_ranking_scores.items():
                    new_note_vals['fm_debug_ranking_info'] += "{}: {:.3f}<br />\n".format(info_name, info_val[note_id])
            if 'fm_debug_words_info' in note:
                new_note_vals['fm_debug_words_info'] = ''
                fields_words_ue_scores_sorted = [dict(sorted(word_dict.items(), key=lambda item: item[1], reverse=True)) for word_dict in note_metrics.words_ue_scores]
                new_note_vals['fm_debug_words_info'] += 'words_ue_scores: '+str(fields_words_ue_scores_sorted)+"<br />\n"
                fields_words_fr_scores_sorted = [dict(sorted(word_dict.items(), key=lambda item: item[1], reverse=True)) for word_dict in note_metrics.words_fr_scores]
                new_note_vals['fm_debug_words_info'] += 'words_fr_scores: '+str(fields_words_fr_scores_sorted)+"<br />\n"
                fields_words_familiarity_sweetspot_scores_sorted = [dict(sorted(word_dict.items(), key=lambda item: item[1], reverse=True))
                                                                    for word_dict in note_metrics.words_familiarity_sweetspot_scores]
                new_note_vals['fm_debug_words_info'] += 'familiarity_sweetspot_scores: '+str(fields_words_familiarity_sweetspot_scores_sorted)+"<br />\n"
                fields_words_familiarity_scores_sorted = [dict(sorted(word_dict.items(), key=lambda item: item[1], reverse=True)) for word_dict in note_metrics.words_familiarity_scores]
                new_note_vals['fm_debug_words_info'] += 'familiarity_scores: '+str(fields_words_familiarity_scores_sorted)+"<br />\n"
            if 'fm_seen_words' in note:
                printed_fields_seen_words = [", ".join(words).strip(", ") for words in note_metrics.seen_words]
                new_note_vals['fm_seen_words'] = " | ".join(printed_fields_seen_words).strip("| ")
            if 'fm_unseen_words' in note:
                printed_fields_unseen_words = [", ".join(words) for words in note_metrics.unseen_words]
                new_note_vals['fm_unseen_words'] = " | ".join(printed_fields_unseen_words).strip("| ")
            if 'fm_focus_words' in note:
                focus_words_per_field: list[str] = []
                for focus_words in note_metrics.focus_words:
                    focus_words = dict(sorted(focus_words.items(), key=lambda item: item[1]))
                    focus_words_per_field.append(", ".join([word for word in focus_words.keys()]))
                new_note_vals['fm_focus_words'] = " | ".join(focus_words_per_field).strip("| ")

            update_note_data = False
            for attr_name, new_attr_val in new_note_vals.items():
                if note[attr_name] != new_attr_val:
                    note[attr_name] = new_attr_val
                    update_note_data = True  # only update if anything is different

            lock_note_data = len(new_note_vals) > 0

            if update_note_data:
                self.modified_dirty_notes[note_id] = note
            elif lock_note_data:  # lock to keep it as it is
                self.modified_dirty_notes[note_id] = None

    def __update_meta_data_for_notes_with_non_new_cards(self, target_cards: TargetCards) -> None:

        notes = target_cards.get_notes()

        notes_metrics = None

        for note_id, note in notes.items():
            if note_id in self.modified_dirty_notes:
                continue

            update_note_data = False
            lock_note_data = False
            field_to_clear = ['fm_debug_info', 'fm_debug_ranking_info', 'fm_debug_words_info', 'fm_seen_words', 'fm_unseen_words']
            for field_name in field_to_clear:
                if field_name in note:
                    lock_note_data = True
                    if note[field_name] != '':
                        note[field_name] = ''
                        update_note_data = True

            if 'fm_focus_words' in note:
                if not notes_metrics:
                    notes_metrics = self.__calc_card_notes_field_metrics(notes, with_additional_props=False)
                lock_note_data = True
                focus_words_per_field: list[str] = []
                for focus_words in notes_metrics[note_id].focus_words:
                    focus_words = dict(sorted(focus_words.items(), key=lambda item: item[1]))
                    focus_words_per_field.append(", ".join([word for word in focus_words.keys()]))
                new_fm_focus_words = " | ".join(focus_words_per_field).strip("| ")
                if new_fm_focus_words != note['fm_focus_words']:
                    note['fm_focus_words'] = new_fm_focus_words
                    update_note_data = True

            if update_note_data:
                self.modified_dirty_notes[note_id] = note
            elif lock_note_data:  # lock to keep it as it is
                self.modified_dirty_notes[note_id] = None
