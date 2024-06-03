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

from .text_processing import WordToken
from .lib.utilities import *
from .target_corpus_data import CorpusSegmentId, TargetCorpusData, TargetNoteFieldContentData
from .language_data import LanguageData
from .target_cards import TargetCards


def sigmoid(x: float) -> float:
    return 1 / (1 + exp(-x))


@dataclass
class FieldMetrics:
    words_fr_scores: dict[WordToken, float] = field(default_factory=dict)
    words_ue_scores: dict[WordToken, float] = field(default_factory=dict)

    words_familiarity_sweetspot_scores: dict[WordToken, float] = field(default_factory=dict)
    words_familiarity_scores: dict[WordToken, float] = field(default_factory=dict)
    words_familiarity_positional_scores: dict[WordToken, float] = field(default_factory=dict)
    focus_words: dict[WordToken, float] = field(default_factory=dict)
    lowest_familiarity_word: Tuple[WordToken, float] = (WordToken(""), 0)

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
    lowest_familiarity_word: list[Tuple[WordToken, float]] = field(default_factory=list)

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

    reinforce_focus_words_scores: list[float] = field(default_factory=list)
    ideal_unseen_words_count_scores: list[float] = field(default_factory=list)
    ideal_words_count_scores: list[float] = field(default_factory=list)
    ideal_focus_words_count_scores: list[float] = field(default_factory=list)


class CardRanker:

    modified_dirty_notes: dict[NoteId, Optional[Note]]
    ranking_factors_span: dict[str, float]
    target_name: str
    ranking_factors_stats: Optional[dict[str, dict[str, float]]]
    ideal_word_count_min: int
    ideal_word_count_max: int

    field_all_empty: dict[str, bool]

    def __init__(self, target_corpus_data: TargetCorpusData, language_data: LanguageData,
                 col: Collection, modified_dirty_notes: dict[NoteId, Optional[Note]]) -> None:

        self.corpus_data = target_corpus_data
        self.language_data = language_data
        self.col = col
        self.modified_dirty_notes = modified_dirty_notes
        self.ranking_factors_stats = None
        self.ranking_factors_span = self.get_default_ranking_factors_span()
        self.target_name = 'undefined'
        self.ideal_word_count_min = 1
        self.ideal_word_count_max = 5
        self.field_all_empty = {}

    @staticmethod
    def get_default_ranking_factors_span() -> dict[str, float]:
        return {
            "word_frequency": 1.0,
            "familiarity": 3.0,
            "familiarity_sweetspot": 1.0,
            "lexical_underexposure": 0.25,
            "ideal_focus_word_count": 1.0,
            "ideal_word_count": 1.0,
            "reinforce_focus_words": 0.25,
            "most_obscure_word": 0.5,
            "lowest_fr_least_familiar_word": 0.25,
            "lowest_word_frequency": 0.25,
            "ideal_unseen_word_count": 0.0,
        }

    @staticmethod
    def __card_field_ideal_word_count_score(word_count: int, ideal_num_min: int, ideal_num_max: int) -> float:
        if word_count >= ideal_num_min and word_count <= ideal_num_max:
            return 1
        middle = (ideal_num_min+ideal_num_max)/2
        difference = abs(middle-word_count)
        score = 1 / (1 + (difference / middle) ** 7)
        if (word_count > 0 and word_count < ideal_num_min):
            return (score + 1) / 2
        return score

    @staticmethod
    def __calc_ideal_unseen_words_count_score(num_unseen_words: int) -> float:
        if (num_unseen_words < 1):
            return 0.9
        score = min(1, abs(0-(1.4*1/min(num_unseen_words, 10))))
        return score

    def calc_cards_ranking(self, target_cards: TargetCards, reorder_scope_target_cards: TargetCards) -> dict[CardId, float]:

        # card ranking is calculates per note (which may have different card, but same ranking)

        notes_from_new_cards = target_cards.get_notes_from_new_cards()
        notes_all_card = target_cards.get_notes_from_all_cards()

        # get ranking factors for notes

        notes_metrics = self.__get_notes_field_metrics(notes_all_card, notes_from_new_cards)
        notes_ranking_factors = self.__get_notes_ranking_factors(notes_from_new_cards, notes_metrics)

        # normalize ranking of notes in reorder scope

        notes_ranking_scores_normalized, notes_rankings = self.__calc_notes_ranking(notes_ranking_factors, reorder_scope_target_cards)

        # set meta data that will be saved in note fields
        self.__set_fields_meta_data_for_notes(notes_all_card, notes_from_new_cards, notes_ranking_scores_normalized, notes_metrics)

        # cards ranking based on note ranking
        card_rankings: dict[CardId, float] = {}
        for card in reorder_scope_target_cards.new_cards:
            card_rankings[card.id] = notes_rankings[card.nid]

        # done
        return card_rankings

    def __calc_notes_ranking(self, notes_ranking_scores: dict[str, dict[NoteId, float]], reorder_scope_target_cards: TargetCards) -> tuple[dict[str, dict[NoteId, float]], dict[NoteId, float]]:

        notes_ranking_scores_normalized: dict[str, dict[NoteId, float]] = {}

        notes_ids = reorder_scope_target_cards.new_cards_notes_ids

        for ranking_factor in notes_ranking_scores.keys():
            notes_ranking_scores_normalized[ranking_factor] = {note_id: ranking_val for (note_id, ranking_val) in notes_ranking_scores[ranking_factor].items() if note_id in notes_ids}

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
            vals = notes_ranking_scores_normalized[attribute].values()
            self.ranking_factors_stats[attribute]['weight'] = self.ranking_factors_span[attribute]
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

        notes_rankings: dict[NoteId, float] = {note_id: 0.0 for note_id in notes_ids}

        for note_id in notes_spanned_ranking_factors.keys():
            total_value = fsum(notes_spanned_ranking_factors[note_id].values())
            span = fsum(self.ranking_factors_span.values())
            notes_rankings[note_id] = total_value/span

        # filter out factors not used in notes_rankings

        useable_notes_ranking_scores_normalized = {attr: notes_ranking_scores_normalized[attr] for attr in notes_ranking_scores_normalized if attr in useable_factors}

        # done

        return useable_notes_ranking_scores_normalized, notes_rankings

    def __get_notes_field_metrics(self, notes_all_card: dict[NoteId, Note], notes_from_new_cards: dict[NoteId, Note]) -> dict[NoteId, AggregatedFieldsMetrics]:

        notes_metrics: dict[NoteId, AggregatedFieldsMetrics] = {note_id: AggregatedFieldsMetrics() for note_id in notes_all_card.keys()}
        bucked_size = fmean([1, (self.ideal_word_count_min+self.ideal_word_count_max)/4])

        for note_id, note in notes_all_card.items():

            # get scores per note field and append to note metrics

            note_fields_defined_in_target = self.corpus_data.targeted_fields_per_note[note.id]
            note_metrics = notes_metrics[note_id]

            for field_data in note_fields_defined_in_target:

                # get metrics for field
                field_metrics = self.__get_field_metrics_from_field_data(field_data, field_data.corpus_segment_id)

                # append existing field metrics (additional metrics created and added below)
                note_metrics.seen_words.append(field_metrics.seen_words)
                note_metrics.unseen_words.append(field_metrics.unseen_words)
                note_metrics.lowest_fr_word.append(field_metrics.lowest_fr_word)
                note_metrics.lowest_familiarity_word.append(field_metrics.lowest_familiarity_word)
                note_metrics.lowest_fr_least_familiar_word.append(field_metrics.lowest_fr_least_familiar_word)
                note_metrics.most_obscure_word.append(field_metrics.most_obscure_word)
                note_metrics.highest_ue_word.append(field_metrics.highest_ue_word)
                note_metrics.words_fr_scores.append(field_metrics.words_fr_scores)
                note_metrics.words_ue_scores.append(field_metrics.words_ue_scores)
                note_metrics.words_familiarity_sweetspot_scores.append(field_metrics.words_familiarity_sweetspot_scores)
                note_metrics.words_familiarity_scores.append(field_metrics.words_familiarity_scores)
                note_metrics.focus_words.append(field_metrics.focus_words)

                if note_id not in notes_from_new_cards:
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

                # reinforce focus words (note has focus word already familiar to user)
                if len(field_metrics.unseen_words) == 0 and len(field_metrics.focus_words) > 0:
                    reinforce_focus_words_score = 1
                else:
                    reinforce_focus_words_score = 0
                note_metrics.reinforce_focus_words_scores.append(reinforce_focus_words_score)

                # familiarity scores (push down)
                if len(field_metrics.words_familiarity_positional_scores) > 0:
                    familiarity_positional_scores = field_metrics.words_familiarity_positional_scores.values()
                    field_familiarity_score = (median(familiarity_positional_scores) + (min(familiarity_positional_scores)*99)) / 100
                    note_metrics.familiarity_scores.append(field_familiarity_score)
                else:
                    note_metrics.familiarity_scores.append(0)

                # familiarity sweetspot scores (push up)
                if len(field_metrics.words_familiarity_sweetspot_scores) > 0:
                    familiarity_sweetspot_scores = field_metrics.words_familiarity_sweetspot_scores.values()
                    bucked_score = min([bucked_size, fsum(familiarity_sweetspot_scores)]) / bucked_size
                    field_familiarity_sweetspot_score = ((bucked_score*2) + fmean(familiarity_sweetspot_scores) + max(familiarity_sweetspot_scores)) / 4
                    note_metrics.familiarity_sweetspot_scores.append(field_familiarity_sweetspot_score)
                else:
                    note_metrics.familiarity_sweetspot_scores.append(0)

                # word frequency scores (push down)
                if (len(field_metrics.fr_scores) > 0):
                    field_fr_score = (median(field_metrics.fr_scores) + (min(field_metrics.fr_scores)*99)) / 100
                    note_metrics.fr_scores.append(field_fr_score)
                else:
                    note_metrics.fr_scores.append(0)

                # underexposure scores (push up)
                if (len(field_metrics.ue_scores) > 0):
                    bucked_score = min([bucked_size, fsum(field_metrics.ue_scores)]) / bucked_size
                    field_ue_score = ((bucked_score*2) + fmean(field_metrics.ue_scores) + max(field_metrics.ue_scores)) / 4
                    note_metrics.ue_scores.append(field_ue_score)
                else:
                    note_metrics.ue_scores.append(0)

        return notes_metrics

    def __get_field_metrics_from_field_data(self, field_data: TargetNoteFieldContentData, corpus_segment_id: CorpusSegmentId) -> FieldMetrics:

        field_metrics = FieldMetrics()
        content_metrics = self.corpus_data.content_metrics[corpus_segment_id]

        for word in field_data.field_value_tokenized:

            # skip if word is in ignore list
            if self.language_data.is_ignore_word(field_data.target_language_data_id, word):
                continue

            # word frequency
            word_fr = content_metrics.word_frequency.get(word, 0)
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

            # lowest familiarity word
            if field_metrics.lowest_familiarity_word[0] == "" or word_familiarity_score < field_metrics.lowest_familiarity_word[1]:
                field_metrics.lowest_familiarity_word = (word, word_familiarity_score)

            # familiarity sweetspot score of words in sweetspot range
            word_familiarity_sweetspot_score = content_metrics.reviewed.words_familiarity_sweetspot.get(word, 0)
            field_metrics.words_familiarity_sweetspot_scores[word] = word_familiarity_sweetspot_score

            # most obscure word (lowest ubiquity)
            word_ubiquity_score = max(word_fr, words_familiarity_positional)
            if field_metrics.most_obscure_word[0] == "" or word_ubiquity_score < field_metrics.most_obscure_word[1]:
                field_metrics.most_obscure_word = (word, word_ubiquity_score)

            # focus words
            if word_familiarity_score < self.corpus_data.focus_words_max_familiarity:
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

        field_metrics.focus_words = dict(sorted(field_metrics.focus_words.items(), key=lambda item: item[1]))

        return field_metrics

    def __get_notes_ranking_factors(self, notes_from_new_cards: dict[NoteId, Note], notes_metrics: dict[NoteId, AggregatedFieldsMetrics]) -> dict[str, dict[NoteId, float]]:

        notes_ranking_factors: dict[str, dict[NoteId, float]] = defaultdict(dict)

        for note_id in notes_from_new_cards.keys():

            note_metrics = notes_metrics[note_id]

            # define ranking factors for note, based on avg of fields

            notes_ranking_factors['word_frequency'][note_id] = fmean(note_metrics.fr_scores)
            notes_ranking_factors['familiarity'][note_id] = fmean(note_metrics.familiarity_scores)
            notes_ranking_factors['reinforce_focus_words'][note_id] = fmean(note_metrics.reinforce_focus_words_scores)

            most_obscure_word_scores = [most_obscure_word[1] for most_obscure_word in note_metrics.most_obscure_word]
            notes_ranking_factors['most_obscure_word'][note_id] = fmean(most_obscure_word_scores)

            lowest_fr_least_familiar_word = [lowest_fr_unseen_word[1] for lowest_fr_unseen_word in note_metrics.lowest_fr_least_familiar_word]

            notes_ranking_factors['lowest_fr_least_familiar_word'][note_id] = fmean(lowest_fr_least_familiar_word)
            notes_ranking_factors['lowest_word_frequency'][note_id] = fmean([lowest_fr_word[1] for lowest_fr_word in note_metrics.lowest_fr_word])

            notes_ranking_factors['ideal_word_count'][note_id] = fmean(note_metrics.ideal_words_count_scores)
            notes_ranking_factors['ideal_focus_word_count'][note_id] = fmean(note_metrics.ideal_focus_words_count_scores)
            notes_ranking_factors['ideal_unseen_word_count'][note_id] = fmean(note_metrics.ideal_unseen_words_count_scores)

            notes_ranking_factors['lexical_underexposure'][note_id] = fmean(note_metrics.ue_scores)
            notes_ranking_factors['familiarity_sweetspot'][note_id] = fmean(note_metrics.familiarity_sweetspot_scores)

        return notes_ranking_factors

    def __field_is_empty_for_all_notes(self, field_name: str, notes_all_card: dict[NoteId, Note]) -> bool:

        if field_name in self.field_all_empty:
            return self.field_all_empty[field_name]

        for note in notes_all_card.values():
            if note[field_name] != '':
                self.field_all_empty[field_name] = False
                return False

        self.field_all_empty[field_name] = True
        return True

    def __set_fields_meta_data_for_notes(self, notes_all_card: dict[NoteId, Note], notes_new_card: dict[NoteId, Note], notes_ranking_scores: dict[str, dict[NoteId, float]],
                                         notes_metrics: dict[NoteId, AggregatedFieldsMetrics]) -> None:

        for note_id, note in notes_all_card.items():

            if note_id in self.modified_dirty_notes:
                continue

            # get new meta data for note fields
            note_metrics = notes_metrics[note_id]
            new_field_data = self.__get_new_meta_data_for_note(note, note_metrics, notes_all_card)
            # add debug info
            new_field_data.update(self.__get_new_debug_info_for_note(note, note_metrics, notes_ranking_scores, notes_new_card))

            # check if update is needed, else lock to prevent other targets from overwriting
            update_note_data = False
            for attr_name, new_attr_val in new_field_data.items():
                if note[attr_name] != new_attr_val:
                    note[attr_name] = new_attr_val
                    update_note_data = True  # only update if anything is different

            lock_note_data = len(new_field_data) > 0

            if update_note_data:
                self.modified_dirty_notes[note_id] = note
            elif lock_note_data:  # lock to keep it as it is
                self.modified_dirty_notes[note_id] = None


    def __get_new_meta_data_for_note(self, note: Note, note_metrics: AggregatedFieldsMetrics, notes_all_card: dict[NoteId, Note]) -> dict[str, str]:

        note_data: dict[str, str] = {}

        # set fm_seen_words
        if 'fm_seen_words' in note:
            seen_words_per_field: list[str] = []
            for field_index, seen_words in enumerate(note_metrics.seen_words):
                if seen_words:
                    seen_words_per_field.append('<span data-field-index="'+str(field_index)+'">'+", ".join(seen_words).strip(", ")+'</span>')
            if seen_words_per_field:
                words_lists = ' <span class="separator">/</span> '.join(seen_words_per_field)
                note_data['fm_seen_words'] = '<span id="fm_seen_words">'+words_lists+'</span>'
            else:
                note_data['fm_seen_words'] = ''

        # set fm_unseen_words
        if 'fm_unseen_words' in note:
            unseen_words_per_field: list[str] = []
            for field_index, unseen_words in enumerate(note_metrics.unseen_words):
                if unseen_words:
                    unseen_words_per_field.append('<span data-field-index="'+str(field_index)+'">'+", ".join(unseen_words).strip(", ")+'</span>')
            if unseen_words_per_field:
                words_lists = ' <span class="separator">/</span> '.join(unseen_words_per_field)
                note_data['fm_unseen_words'] = '<span id="fm_unseen_words">'+words_lists+'</span>'
            else:
                note_data['fm_unseen_words'] = ''

        # set fm_focus_words
        if 'fm_focus_words' in note:
            focus_words_per_field: list[str] = []
            for field_index, focus_words in enumerate(note_metrics.focus_words):
                if focus_words:
                    focus_words_str = '<span data-field-index="'+str(field_index)+'">'+", ".join([word for word in focus_words.keys()])+'</span>'
                    focus_words_per_field.append(focus_words_str)
            if focus_words_per_field:
                words_lists = ' <span class="separator">/</span> '.join(focus_words_per_field)
                note_data['fm_focus_words'] = '<span id="fm_focus_words">'+words_lists+'</span>'
            else:
                note_data['fm_focus_words'] = ''

        # set fm_lowest_fr_word_[n]
        for index, field_lowest_fr_word in enumerate(note_metrics.lowest_fr_word):
            field_name = 'fm_lowest_fr_word_'+str(index)
            if field_name in note:
                note_data[field_name] = field_lowest_fr_word[0]

        # set fm_lowest_familiarity_word_[n]
        for index, field_lowest_familiarity_word in enumerate(note_metrics.lowest_familiarity_word):
            field_name = 'fm_lowest_familiarity_word_'+str(index)
            field_name_static = 'fm_lowest_familiarity_word_static_'+str(index)
            if field_name in note:
                note_data[field_name] = field_lowest_familiarity_word[0]
            if field_name_static in note and self.__field_is_empty_for_all_notes(field_name_static, notes_all_card):
                note_data[field_name_static] = field_lowest_familiarity_word[0]

        # set fm_main_focus_word_[n]
        for index, focus_words in enumerate(note_metrics.focus_words):
            field_name = 'fm_main_focus_word_'+str(index)
            field_name_static = 'fm_main_focus_word_static_'+str(index)
            if field_name in note:
                if focus_words:
                    note_data[field_name] = list(focus_words.keys())[0]
                else:
                    note_data[field_name] = ''
            if field_name_static in note and self.__field_is_empty_for_all_notes(field_name_static, notes_all_card):
                if focus_words:
                    note_data[field_name_static] = list(focus_words.keys())[0]
                else:
                    note_data[field_name_static] = ''

        return note_data

    def __get_new_debug_info_for_note(self, note: Note, note_metrics: AggregatedFieldsMetrics, notes_ranking_scores: dict[str, dict[NoteId, float]],
                                     notes_new_card: dict[NoteId, Note]) -> dict[str, str]:

        try:
            reorder_scope_note_ids = list(list(notes_ranking_scores.values())[0].keys())
        except:
            reorder_scope_note_ids = []

        note_data: dict[str, str] = {}

        # set fm_debug_info
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
            note_data['fm_debug_info'] = 'Target '+self.target_name+'<br />'
            for info_name, info_val in debug_info.items():
                if info_val:
                    fields_info = " | ".join([str(field_info) for field_info in info_val]).strip("| ")
                    note_data['fm_debug_info'] += info_name+": " + fields_info+"<br />\n"

        # set fm_debug_ranking_info
        if 'fm_debug_ranking_info' in note:
            if note.id in notes_new_card:
                if not note.id in reorder_scope_note_ids:
                    note_data['fm_debug_ranking_info'] = '<< Not in reorder scope of target '+self.target_name+' >>'
                else:
                    note_data['fm_debug_ranking_info'] = 'Target '+self.target_name+'<br />'
                    used_ranking_factors = {k: v for k, v in notes_ranking_scores.items() if k in self.ranking_factors_span and self.ranking_factors_span[k] > 0}
                    ranking_scores = dict(sorted(used_ranking_factors.items(), key=lambda item: (item[1][note.id]*self.ranking_factors_span[item[0]]), reverse=True))
                    for factor_name, factor_values in ranking_scores.items():
                        factor_value = factor_values[note.id]
                        factor_span = self.ranking_factors_span[factor_name]
                        factor_score = factor_value*factor_span
                        note_data['fm_debug_ranking_info'] += "{}: {:.3f} <span style=\"opacity:0.5;\">x {} = {:.3f}</span><br />\n".format(factor_name, factor_value, factor_span, factor_score)
            else:
                note_data['fm_debug_ranking_info'] = '<< No new cards in main scope of target '+self.target_name+' >>'

        # set fm_debug_words_info
        if 'fm_debug_words_info' in note:
            note_data['fm_debug_words_info'] = 'Target '+self.target_name+'<br />'
            fields_words_ue_scores_sorted = [dict(sorted(word_dict.items(), key=lambda item: item[1], reverse=True)) for word_dict in note_metrics.words_ue_scores]
            note_data['fm_debug_words_info'] += 'words_ue_scores: '+str(fields_words_ue_scores_sorted)+"<br />\n"
            fields_words_fr_scores_sorted = [dict(sorted(word_dict.items(), key=lambda item: item[1], reverse=True)) for word_dict in note_metrics.words_fr_scores]
            note_data['fm_debug_words_info'] += 'words_fr_scores: '+str(fields_words_fr_scores_sorted)+"<br />\n"
            fields_words_familiarity_sweetspot_scores_sorted = [dict(sorted(word_dict.items(), key=lambda item: item[1], reverse=True))
                                                                for word_dict in note_metrics.words_familiarity_sweetspot_scores]
            note_data['fm_debug_words_info'] += 'familiarity_sweetspot_scores: '+str(fields_words_familiarity_sweetspot_scores_sorted)+"<br />\n"
            fields_words_familiarity_scores_sorted = [dict(sorted(word_dict.items(), key=lambda item: item[1], reverse=True)) for word_dict in note_metrics.words_familiarity_scores]
            note_data['fm_debug_words_info'] += 'familiarity_scores: '+str(fields_words_familiarity_scores_sorted)+"<br />\n"

        return note_data
