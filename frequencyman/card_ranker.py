"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from math import fsum, log
from statistics import fmean, median
from typing import Optional

from anki.cards import Card, CardId
from anki.notes import Note, NoteId
from anki.collection import Collection

from .text_processing import WordToken
from .lib.utilities import *
from .target_corpus_data import CorpusSegmentId, TargetCorpusData, NoteFieldContentData
from .language_data import LanguageData
from .target_cards import TargetCards


@dataclass_with_slots()
class FieldMetrics:
    words_fr_scores: dict[WordToken, float] = field(default_factory=dict)
    words_ue_scores: dict[WordToken, float] = field(default_factory=dict)

    words_familiarity_sweetspot_scores: dict[WordToken, float] = field(default_factory=dict)
    words_familiarity_scores: dict[WordToken, float] = field(default_factory=dict)
    words_familiarity_positional_scores: dict[WordToken, float] = field(default_factory=dict)
    focus_words: dict[WordToken, float] = field(default_factory=dict)

    num_words: int = 0
    unique_words: set[WordToken] = field(default_factory=set)
    seen_words: list[WordToken] = field(default_factory=list)
    new_words: list[WordToken] = field(default_factory=list)

    lowest_familiarity_word: tuple[WordToken, float] = (WordToken(""), 0)
    lowest_fr_least_familiar_word: tuple[WordToken, float, float] = (WordToken(""), 0, 0)
    lowest_fr_word: tuple[WordToken, float] = (WordToken(""), 0)

    highest_ue_word: tuple[WordToken, float] = (WordToken(""), 0)
    most_obscure_word: tuple[WordToken, float] = (WordToken(""), 0)

    fr_scores: list[float] = field(default_factory=list)
    ue_scores: list[float] = field(default_factory=list)

    ideal_new_words_count_score: float = 0
    ideal_focus_words_count_score: float = 0
    ideal_words_count_score: float = 0
    new_words_score: float = 0
    no_new_words_score: float = 0
    reinforce_learning_words_score: float = 0
    proper_introduction_score: float = 0
    proper_introduction_dispersed_score: float = 0

    familiarity_score: float = 0
    familiarity_sweetspot_score: float = 0

    fr_score: float = 0
    ue_score: float = 0


class CardRanker:

    modified_dirty_notes: dict[NoteId, Optional[Note]]
    ranking_factors_span: dict[str, float]
    target_name: str
    ranking_factors_stats: Optional[dict[str, dict[str, float]]]
    ideal_word_count_min: int
    ideal_word_count_max: int

    field_all_empty: dict[str, bool]
    note_model_has_n_field: dict[str, bool]

    def __init__(self, target_corpus_data: TargetCorpusData, target_name: str, language_data: LanguageData,
                 modified_dirty_notes: dict[NoteId, Optional[Note]]) -> None:

        self.corpus_data = target_corpus_data
        self.language_data = language_data
        self.modified_dirty_notes = modified_dirty_notes
        self.ranking_factors_stats = None
        self.ranking_factors_span = self.get_default_ranking_factors_span()
        self.target_name = target_name
        self.ideal_word_count_min = 1
        self.ideal_word_count_max = 5
        self.field_all_empty = {}
        self.note_model_has_n_field = {}

    @staticmethod
    def get_default_ranking_factors_span() -> dict[str, float]:
        return {
            "word_frequency": 1.0,
            "familiarity": 1.0,
            "familiarity_sweetspot": 0.5,
            "lexical_underexposure": 0.25,
            "ideal_focus_word_count": 4.0,
            "ideal_word_count": 1.0,
            "reinforce_learning_words": 1.5,
            "most_obscure_word": 0.5,
            "lowest_fr_least_familiar_word": 0.25,
            "lowest_word_frequency": 1.0,
            "lowest_familiarity": 1.0,
            "new_words": 0.5,
            "no_new_words": 0.0,
            "ideal_new_word_count": 0.0,
            "proper_introduction": 0.1,
            "proper_introduction_dispersed": 0.0
        }

    @staticmethod
    def __calc_ideal_word_count_score(word_count: int, ideal_num_min: int, ideal_num_max: int) -> float:
        if word_count >= ideal_num_min and word_count <= ideal_num_max:
            return 1
        middle = (ideal_num_min+ideal_num_max)/2
        difference = abs(middle-word_count)
        score = 1 / (1 + (difference / middle) ** 3.5)
        if (word_count > 0 and word_count < ideal_num_min):
            return (score + 1) / 2
        return score

    @staticmethod
    def __calc_ideal_np1_score(num_new_words: int) -> float:
        if num_new_words == 0:
            score_devalue_factor = 0.5
        elif num_new_words == 1:
            score_devalue_factor = 0
        else:
            score_devalue_factor = num_new_words

        score = 1 / (2**score_devalue_factor)
        return score

    @staticmethod
    def __calc_proper_introduction_score(field_metrics: FieldMetrics, field_data: NoteFieldContentData) -> tuple[Optional[WordToken], float]:

        if not field_data.field_value_tokenized or field_metrics.lowest_fr_least_familiar_word[0] == "":
            return (None, 0)

        assert len(field_metrics.words_familiarity_positional_scores) == len(field_metrics.words_fr_scores)
        assert field_metrics.lowest_fr_least_familiar_word[0] in field_data.field_value_tokenized

        # get new word
        intro_word = field_metrics.lowest_fr_least_familiar_word[0]

        # position of new word in field
        intro_word_index = field_data.field_value_tokenized.index(intro_word)
        intro_word_position_score = 1 / (1 + (intro_word_index / 4))

        # single new word factor
        num_new_words = len(field_metrics.new_words)
        single_new_word_score = 0.0 if num_new_words > 1 else 1.0

        # no repeat factor
        intro_word_no_repeat_factor = 1 / field_data.field_value_tokenized.count(intro_word)
        general_no_repeat_factor = 1 / (1 + (field_metrics.num_words - len(field_metrics.unique_words)))
        no_repeat_score = (intro_word_no_repeat_factor + general_no_repeat_factor + 1) / 3

        # non-obscurity of other words

        other_words = [word for word in field_metrics.words_fr_scores.keys() if word != intro_word]
        non_obscurity_others_words_score = 0.0

        if other_words:
            lowest_wf_other_words = min(field_metrics.words_fr_scores[word] for word in other_words)
            lowest_familiarity_other_words = min(field_metrics.words_familiarity_positional_scores[word] for word in other_words)
            non_obscurity_others_words_score = (min(lowest_wf_other_words, lowest_familiarity_other_words) +
                                                (lowest_wf_other_words + lowest_familiarity_other_words) / 2) / 2

        assert non_obscurity_others_words_score <= 1

        # proper introduction score

        factors = [
            field_metrics.ideal_focus_words_count_score,
            field_metrics.ideal_words_count_score,
            intro_word_position_score,
            single_new_word_score,
            no_repeat_score,
            non_obscurity_others_words_score
        ]

        proper_introduction_score = fmean(factors)

        return (intro_word, proper_introduction_score)

    def calc_cards_ranking(self, target_cards: TargetCards, reorder_scope_target_cards: TargetCards) -> dict[CardId, float]:

        # boost weight of lowest_word_frequency if there are not enough reviewed cards for other factors to be useful

        if len(target_cards.reviewed_cards) < 50 and len(self.ranking_factors_span) == len(self.get_default_ranking_factors_span()):
            self.ranking_factors_span['lowest_word_frequency'] = max(fsum(self.ranking_factors_span.values()), self.ranking_factors_span['lowest_word_frequency'])

        # card ranking is calculates per note (which may have different cards, but same ranking)

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

        notes_ids = set(reorder_scope_target_cards.new_cards_notes_ids)

        for ranking_factor in notes_ranking_scores.keys():
            notes_ranking_scores_normalized[ranking_factor] = {note_id: ranking_val for (note_id, ranking_val) in notes_ranking_scores[ranking_factor].items() if note_id in notes_ids}

        useable_factors: set[str] = set()

        # perform Z-score standardization, then 0 to 1 normalization

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

        notes_rankings: dict[NoteId, float] = dict.fromkeys(notes_ids, 0.0)
        ranking_factors_span_sum = fsum(self.ranking_factors_span.values())

        for note_id in notes_spanned_ranking_factors.keys():
            total_value = fsum(notes_spanned_ranking_factors[note_id].values())
            notes_rankings[note_id] = total_value/ranking_factors_span_sum

        # filter out factors not used in notes_rankings

        useable_notes_ranking_scores_normalized = {attr: notes_ranking_scores_normalized[attr] for attr in notes_ranking_scores_normalized if attr in useable_factors}

        # done

        return useable_notes_ranking_scores_normalized, notes_rankings

    def __is_factor_used(self, factor_name: str) -> bool:

        try:
            return self.ranking_factors_span[factor_name] > 0
        except KeyError:
            return False

    def __get_notes_field_metrics(self, notes_all_card: dict[NoteId, Note], notes_from_new_cards: dict[NoteId, Note]) -> dict[NoteId, list[FieldMetrics]]:

        notes_metrics: dict[NoteId, list[FieldMetrics]] = {note_id: [] for note_id in notes_all_card.keys()}
        bucked_size = fmean([1, (self.ideal_word_count_min+self.ideal_word_count_max)/4])
        set_proper_introduction = self.__is_factor_used('proper_introduction')
        set_proper_introduction_dispersed = self.__is_factor_used('proper_introduction_dispersed')
        introducing_notes: dict[WordToken, list[tuple[NoteId, float, int]]] = defaultdict(list)

        for note_id, note in notes_all_card.items():

            # get scores per note field and append to note metrics

            note_fields_defined_in_target = self.corpus_data.targeted_fields_per_note[note.id]

            for field_data in note_fields_defined_in_target:

                # get metrics for field
                field_metrics = self.__get_field_metrics_from_field_data(field_data, field_data.corpus_segment_id)

                # add to field metrics for note, add more to field_metrics below
                notes_metrics[note_id].append(field_metrics)
                notes_metrics_index = len(notes_metrics[note_id])-1

                # some metrics are not needed for reviewed cards
                if note_id not in notes_from_new_cards:
                    continue

                # ideal new words count
                field_ideal_new_words_count_score = self.__calc_ideal_np1_score(len(field_metrics.new_words))
                field_metrics.ideal_new_words_count_score = field_ideal_new_words_count_score

                # ideal focus words count
                field_ideal_focus_words_count_score = self.__calc_ideal_np1_score(len(field_metrics.focus_words))
                field_metrics.ideal_focus_words_count_score = field_ideal_focus_words_count_score

                # ideal word count
                field_ideal_word_count_score = self.__calc_ideal_word_count_score(len(field_data.field_value_tokenized), self.ideal_word_count_min, self.ideal_word_count_max)
                field_metrics.ideal_words_count_score = field_ideal_word_count_score

                # new words
                field_new_words_score = 1 if len(field_metrics.new_words) > 0 else 0
                field_metrics.new_words_score = field_new_words_score
                field_no_new_words_score = 1 if len(field_metrics.new_words) == 0 else 0
                field_metrics.no_new_words_score = field_no_new_words_score

                # proper introduction
                if set_proper_introduction or set_proper_introduction_dispersed:
                    (new_word, proper_introduction_score) = self.__calc_proper_introduction_score(field_metrics, field_data)
                    if len(field_metrics.new_words) == 0:
                        field_metrics.proper_introduction_score = 1
                    else:
                        field_metrics.proper_introduction_score = proper_introduction_score
                    field_metrics.proper_introduction_dispersed_score = proper_introduction_score
                    if set_proper_introduction_dispersed and new_word is not None:
                        introducing_notes[new_word].append((note_id, proper_introduction_score, notes_metrics_index))

                # reinforce learning words (note has no new words, but has at least one learning / non-mature word)
                field_metrics.reinforce_learning_words_score = 0
                if len(field_metrics.new_words) == 0 and len(field_metrics.focus_words) > 0:
                    field_metrics.reinforce_learning_words_score = 1

                # familiarity scores (push down)
                if len(field_metrics.words_familiarity_positional_scores) > 0:
                    familiarity_positional_scores = field_metrics.words_familiarity_positional_scores.values()
                    field_familiarity_score = (median(familiarity_positional_scores) + (min(familiarity_positional_scores)*99)) / 100
                    field_metrics.familiarity_score = field_familiarity_score

                # familiarity sweetspot scores (push up)
                if len(field_metrics.words_familiarity_sweetspot_scores) > 0:
                    familiarity_sweetspot_scores = field_metrics.words_familiarity_sweetspot_scores.values()
                    bucked_score = min([bucked_size, fsum(familiarity_sweetspot_scores)]) / bucked_size
                    field_familiarity_sweetspot_score = ((bucked_score*2) + fmean(familiarity_sweetspot_scores) + max(familiarity_sweetspot_scores)) / 4
                    field_metrics.familiarity_sweetspot_score = field_familiarity_sweetspot_score

                # word frequency scores (push down)
                if (len(field_metrics.fr_scores) > 0):
                    field_fr_score = (median(field_metrics.fr_scores) + (min(field_metrics.fr_scores)*99)) / 100
                    field_metrics.fr_score = field_fr_score

                # underexposure scores (push up)
                if (len(field_metrics.ue_scores) > 0):
                    bucked_score = min([bucked_size, fsum(field_metrics.ue_scores)]) / bucked_size
                    field_ue_score = ((bucked_score*2) + fmean(field_metrics.ue_scores) + max(field_metrics.ue_scores)) / 4
                    if field_ue_score > 0 and field_metrics.lowest_familiarity_word[1] > 2.5 and (ue_devalue := log(field_metrics.lowest_familiarity_word[1])) > 1.0:
                        field_ue_score = field_ue_score / ue_devalue
                    field_metrics.ue_score = field_ue_score

        if set_proper_introduction_dispersed:
            for introducing_notes_list in introducing_notes.values():
                introducing_notes_list.sort(key=lambda x: x[1], reverse=True)
                for position, (note_id, proper_introduction_score, metric_index) in enumerate(introducing_notes_list):
                    new_proper_introduction_dispersed_score = 1 / (2**position)
                    notes_metrics[note_id][metric_index].proper_introduction_dispersed_score = new_proper_introduction_dispersed_score

        # done

        return notes_metrics

    def __get_field_metrics_from_field_data(self, field_data: NoteFieldContentData, corpus_segment_id: CorpusSegmentId) -> FieldMetrics:

        field_metrics = FieldMetrics()
        content_metrics = self.corpus_data.content_metrics[corpus_segment_id]
        set_lexical_underexposure = self.__is_factor_used('lexical_underexposure')
        set_familiarity_sweetspot = self.__is_factor_used('familiarity_sweetspot')
        ignored_words = self.language_data.get_ignored_words(field_data.target_language_data_id)

        for word in field_data.field_value_tokenized:

            # skip if word is in ignore list
            if word in ignored_words:
                continue

            # word frequency
            word_fr = content_metrics.word_frequency.get(word, 0)
            field_metrics.fr_scores.append(word_fr)
            field_metrics.words_fr_scores[word] = word_fr

            # lowest fr word
            if field_metrics.lowest_fr_word[0] == "" or word_fr < field_metrics.lowest_fr_word[1]:
                field_metrics.lowest_fr_word = (word, word_fr)

            # lexical underexposure
            if set_lexical_underexposure:
                word_ue = content_metrics.words_underexposure.get(word, 0)
                field_metrics.ue_scores.append(word_ue)
                field_metrics.words_ue_scores[word] = word_ue

                # most underexposure word
                if field_metrics.highest_ue_word[0] == "" or word_ue > field_metrics.highest_ue_word[1]:
                    field_metrics.highest_ue_word = (word, word_ue)

            #  familiarity score of words
            word_familiarity_score = content_metrics.words_familiarity.get(word, 0)
            field_metrics.words_familiarity_scores[word] = word_familiarity_score

            words_familiarity_positional = content_metrics.words_familiarity_positional.get(word, 0)
            field_metrics.words_familiarity_positional_scores[word] = words_familiarity_positional

            # lowest familiarity word
            if field_metrics.lowest_familiarity_word[0] == "" or word_familiarity_score < field_metrics.lowest_familiarity_word[1]:
                field_metrics.lowest_familiarity_word = (word, word_familiarity_score)

            # familiarity sweetspot score of words in sweetspot range
            if set_familiarity_sweetspot:
                word_familiarity_sweetspot_score = content_metrics.words_familiarity_sweetspot.get(word, 0)
                field_metrics.words_familiarity_sweetspot_scores[word] = word_familiarity_sweetspot_score

            # most obscure word (lowest ubiquity)
            word_ubiquity_score = max(word_fr, words_familiarity_positional)
            if field_metrics.most_obscure_word[0] == "" or word_ubiquity_score < field_metrics.most_obscure_word[1]:
                field_metrics.most_obscure_word = (word, word_ubiquity_score)

            # focus words
            if word not in content_metrics.mature_words:
                field_metrics.focus_words[word] = word_familiarity_score

            # set unique, seen and new words
            if word not in field_metrics.unique_words:
                field_metrics.unique_words.add(word)
                if word in content_metrics.reviewed_words:
                    field_metrics.seen_words.append(word)  # word seen, word exist in at least one reviewed card
                else:
                    field_metrics.new_words.append(word)

            # set lowest fr of least familiar word
            if field_metrics.lowest_fr_least_familiar_word[0] == "" or word_familiarity_score < field_metrics.lowest_fr_least_familiar_word[2]:
                field_metrics.lowest_fr_least_familiar_word = (word, word_fr, word_familiarity_score)
            elif word_familiarity_score == field_metrics.lowest_fr_least_familiar_word[2]:
                if word_fr < field_metrics.lowest_fr_least_familiar_word[1]:
                    field_metrics.lowest_fr_least_familiar_word = (word, word_fr, word_familiarity_score)

        field_metrics.num_words = len(field_data.field_value_tokenized)
        field_metrics.focus_words = dict(sorted(field_metrics.focus_words.items(), key=lambda item: item[1]))

        return field_metrics

    def __get_notes_ranking_factors(self, notes_from_new_cards: dict[NoteId, Note], notes_metrics: dict[NoteId, list[FieldMetrics]]) -> dict[str, dict[NoteId, float]]:

        notes_ranking_factors: dict[str, dict[NoteId, float]] = defaultdict(dict)

        for note_id in notes_from_new_cards.keys():

            note_metrics = notes_metrics[note_id]

            # define ranking factors for note, based on avg of fields

            notes_ranking_factors['word_frequency'][note_id] = fmean(field_metrics.fr_score for field_metrics in note_metrics)
            notes_ranking_factors['familiarity'][note_id] = fmean(field_metrics.familiarity_score for field_metrics in note_metrics)

            most_obscure_word_scores = [field_metrics.most_obscure_word[1] for field_metrics in note_metrics]
            notes_ranking_factors['most_obscure_word'][note_id] = (median(most_obscure_word_scores) + (min(most_obscure_word_scores)*9_999)) / 10_000

            lowest_fr_least_familiar_word_scores = [field_metrics.lowest_fr_least_familiar_word[1] for field_metrics in note_metrics]
            notes_ranking_factors['lowest_fr_least_familiar_word'][note_id] = (median(lowest_fr_least_familiar_word_scores) + (min(lowest_fr_least_familiar_word_scores)*9_999)) / 10_000

            lowest_word_frequency_scores = [field_metrics.lowest_fr_word[1] for field_metrics in note_metrics]
            notes_ranking_factors['lowest_word_frequency'][note_id] = (median(lowest_word_frequency_scores) + (min(lowest_word_frequency_scores)*9_999)) / 10_000

            lowest_familiarity_scores = [field_metrics.lowest_familiarity_word[1] for field_metrics in note_metrics]
            notes_ranking_factors['lowest_familiarity'][note_id] = (median(lowest_familiarity_scores) + (min(lowest_familiarity_scores)*9_999)) / 10_000

            new_words_scores = [field_metrics.new_words_score for field_metrics in note_metrics]
            notes_ranking_factors['new_words'][note_id] = (median(new_words_scores) + (min(new_words_scores)*2)) / 3

            no_new_words_scores = [field_metrics.no_new_words_score for field_metrics in note_metrics]
            notes_ranking_factors['no_new_words'][note_id] = (median(no_new_words_scores) + (min(no_new_words_scores)*2)) / 3

            notes_ranking_factors['proper_introduction'][note_id] = fmean(field_metrics.proper_introduction_score for field_metrics in note_metrics)
            notes_ranking_factors['proper_introduction_dispersed'][note_id] = fmean(field_metrics.proper_introduction_dispersed_score for field_metrics in note_metrics)

            notes_ranking_factors['ideal_word_count'][note_id] = fmean(field_metrics.ideal_words_count_score for field_metrics in note_metrics)
            notes_ranking_factors['ideal_focus_word_count'][note_id] = fmean(field_metrics.ideal_focus_words_count_score for field_metrics in note_metrics)
            notes_ranking_factors['ideal_new_word_count'][note_id] = fmean(field_metrics.ideal_new_words_count_score for field_metrics in note_metrics)

            notes_ranking_factors['lexical_underexposure'][note_id] = fmean(field_metrics.ue_score for field_metrics in note_metrics)
            notes_ranking_factors['familiarity_sweetspot'][note_id] = fmean(field_metrics.familiarity_sweetspot_score for field_metrics in note_metrics)

            has_new_words = any(len(field_metrics.new_words) > 0 for field_metrics in note_metrics)
            if has_new_words:
                notes_ranking_factors['reinforce_learning_words'][note_id] = 0
            else:
                notes_ranking_factors['reinforce_learning_words'][note_id] = fmean(field_metrics.reinforce_learning_words_score for field_metrics in note_metrics)
                if notes_ranking_factors['reinforce_learning_words'][note_id] > 0:
                    notes_ranking_factors['reinforce_learning_words'][note_id] = (1+notes_ranking_factors['reinforce_learning_words'][note_id])/2

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

    def __note_has_n_field(self, note: Note, field_name: str, note_metrics: list[FieldMetrics]) -> bool:

        key = str(note.mid)+'_'+field_name

        if key in self.note_model_has_n_field:
            return self.note_model_has_n_field[key]

        for i in range(len(note_metrics)):
            if field_name+'_'+str(i) in note:
                self.note_model_has_n_field[key] = True
                return True

        self.note_model_has_n_field[key] = False
        return False

    def __set_fields_meta_data_for_notes(self, notes_all_card: dict[NoteId, Note], notes_new_card: dict[NoteId, Note], notes_ranking_scores: dict[str, dict[NoteId, float]],
                                         notes_metrics: dict[NoteId, list[FieldMetrics]]) -> None:

        try:
            reorder_scope_note_ids = set(list(notes_ranking_scores.values())[0].keys())
        except:
            reorder_scope_note_ids = set()

        non_modified_notes = {note_id: note for note_id, note in notes_all_card.items() if note_id not in self.modified_dirty_notes}

        notes_debug_info: dict[NoteId, dict[str, str]] = self.__get_new_debug_info_for_notes(
            non_modified_notes,
            notes_metrics,
            notes_ranking_scores,
            notes_new_card,
            reorder_scope_note_ids
        )

        for note_id, note in non_modified_notes.items():

            # get new meta data for note fields
            note_metrics = notes_metrics[note_id]
            new_field_data = self.__get_new_meta_data_for_note(note, note_metrics, notes_all_card)

            # add debug info
            new_field_data.update(notes_debug_info[note_id])

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

    def __get_new_meta_data_for_note(self, note: Note, note_metrics: list[FieldMetrics], notes_all_card: dict[NoteId, Note]) -> dict[str, str]:

        note_data: dict[str, str] = {}

        # set fm_seen_words
        if 'fm_seen_words' in note:
            seen_words_per_field: list[str] = []
            for field_index, field_metrics in enumerate(note_metrics):
                if field_metrics.seen_words:
                    seen_words_per_field.append('<span data-field-index="'+str(field_index)+'">'+", ".join(field_metrics.seen_words).strip(", ")+'</span>')
            if seen_words_per_field:
                words_lists = ' <span class="separator">/</span> '.join(seen_words_per_field)
                note_data['fm_seen_words'] = '<span id="fm_seen_words">'+words_lists+'</span>'
            else:
                note_data['fm_seen_words'] = ''

        # set fm_new_words
        if 'fm_new_words' in note:
            new_words_per_field: list[str] = []
            for field_index, field_metrics in enumerate(note_metrics):
                if field_metrics.new_words:
                    new_words_per_field.append('<span data-field-index="'+str(field_index)+'">'+", ".join(field_metrics.new_words).strip(", ")+'</span>')
            if new_words_per_field:
                words_lists = ' <span class="separator">/</span> '.join(new_words_per_field)
                note_data['fm_new_words'] = '<span id="fm_new_words">'+words_lists+'</span>'
            else:
                note_data['fm_new_words'] = ''

        # set fm_unseen_words (deprecated, use fm_new_words)
        if 'fm_unseen_words' in note:
            unseen_words_per_field: list[str] = []
            for field_index, field_metrics in enumerate(note_metrics):
                if field_metrics.new_words:
                    unseen_words_per_field.append('<span data-field-index="'+str(field_index)+'">'+", ".join(field_metrics.new_words).strip(", ")+'</span>')
            if unseen_words_per_field:
                words_lists = ' <span class="separator">/</span> '.join(unseen_words_per_field)
                note_data['fm_unseen_words'] = '<span id="fm_new_words">'+words_lists+'</span>'
            else:
                note_data['fm_unseen_words'] = ''

        # set fm_focus_words
        if 'fm_focus_words' in note:
            focus_words_per_field: list[str] = []
            for field_index, field_metrics in enumerate(note_metrics):
                if field_metrics.focus_words:
                    focus_words_str = '<span data-field-index="'+str(field_index)+'">'+", ".join(field_metrics.focus_words.keys())+'</span>'
                    focus_words_per_field.append(focus_words_str)
            if focus_words_per_field:
                words_lists = ' <span class="separator">/</span> '.join(focus_words_per_field)
                note_data['fm_focus_words'] = '<span id="fm_focus_words">'+words_lists+'</span>'
            else:
                note_data['fm_focus_words'] = ''

        # set fm_lowest_fr_word_[n]
        if self.__note_has_n_field(note, 'fm_lowest_fr_word', note_metrics):
            for index, field_metrics in enumerate(note_metrics):
                field_name = 'fm_lowest_fr_word_'+str(index)
                if field_name in note:
                    note_data[field_name] = field_metrics.lowest_fr_word[0]

        # set fm_lowest_familiarity_word_[n]
        if self.__note_has_n_field(note, 'fm_lowest_familiarity_word_static', note_metrics):
            for index, field_metrics in enumerate(note_metrics):
                field_name = 'fm_lowest_familiarity_word_'+str(index)
                field_name_static = 'fm_lowest_familiarity_word_static_'+str(index)
                if field_name in note:
                    note_data[field_name] = field_metrics.lowest_familiarity_word[0]
                if field_name_static in note and self.__field_is_empty_for_all_notes(field_name_static, notes_all_card):
                    note_data[field_name_static] = field_metrics.lowest_familiarity_word[0]

        # set fm_main_focus_word_[n]
        if self.__note_has_n_field(note, 'fm_main_focus_word', note_metrics) or self.__note_has_n_field(note, 'fm_main_focus_word_static', note_metrics):
            for index, field_metrics in enumerate(note_metrics):
                field_name = 'fm_main_focus_word_'+str(index)
                field_name_static = 'fm_main_focus_word_static_'+str(index)
                if field_name in note:
                    if field_metrics.focus_words:
                        note_data[field_name] = list(field_metrics.focus_words.keys())[0]
                    else:
                        note_data[field_name] = ''
                if field_name_static in note and self.__field_is_empty_for_all_notes(field_name_static, notes_all_card):
                    if field_metrics.focus_words:
                        note_data[field_name_static] = list(field_metrics.focus_words.keys())[0]
                    else:
                        note_data[field_name_static] = ''

        return note_data

    def __get_new_debug_info_for_notes(self, notes: dict[NoteId, Note], notes_metrics: dict[NoteId, list[FieldMetrics]], notes_ranking_scores: dict[str, dict[NoteId, float]],
                                       notes_new_card: dict[NoteId, Note], reorder_scope_notes_ids: set[NoteId]) -> dict[NoteId, dict[str, str]]:

        notes_debug_info: dict[NoteId, dict[str, str]] = {}

        set_lexical_underexposure = self.__is_factor_used('lexical_underexposure')
        set_familiarity_sweetspot = self.__is_factor_used('familiarity_sweetspot')
        set_ideal_new_word_count = self.__is_factor_used('ideal_new_word_count')
        set_proper_introduction = self.__is_factor_used('proper_introduction')
        set_proper_introduction_dispersed = self.__is_factor_used('proper_introduction_dispersed')

        def debug_info_float(score: float) -> str:
            return f"{score:.3g}"

        def debug_info_tuple_single(tuple_data: tuple[WordToken, float]) -> str:
            return f"('{tuple_data[0]}', {tuple_data[1]:.3g})"

        def debug_info_tuple_double(tuple_data: tuple[WordToken, float, float]) -> str:
            return f"('{tuple_data[0]}', {tuple_data[1]:.3g}, {tuple_data[2]:.3g})"

        def debug_info_dict(dict_data: dict[WordToken, float]) -> str:
            return "{" + ", ".join(f"'{word}': {score:.3g}" for word, score in dict_data.items()) + "}"

        def debug_info_list_dict(list_data: list[dict[WordToken, float]]) -> str:
            return "[" + ", ".join(debug_info_dict(dict_data) for dict_data in list_data) + "]"

        target_title_html = f'<i style="opacity:0.5">Target {self.target_name}</i><br />'
        debug_info_not_in_reorder_scope = f'<< Not in reorder scope of target {self.target_name} >>'
        debug_info_no_new_cards = f'<< No new cards in main scope of target {self.target_name} >>'

        for note_id, note in notes.items():

            note_metrics = notes_metrics[note_id]

            note_data: dict[str, str] = {}

            # set fm_debug_info
            if 'fm_debug_info' in note:
                debug_info: dict[str, list[str]] = {
                    'fr_scores': [debug_info_float(field_metrics.fr_score) for field_metrics in note_metrics],
                    'familiarity_scores': [debug_info_float(field_metrics.familiarity_score) for field_metrics in note_metrics],
                    'most_obscure_word': [debug_info_tuple_single(field_metrics.most_obscure_word) for field_metrics in note_metrics],
                    'ideal_focus_word_count': [debug_info_float(field_metrics.ideal_focus_words_count_score) for field_metrics in note_metrics],
                    'ideal_word_count': [debug_info_float(field_metrics.ideal_words_count_score) for field_metrics in note_metrics],
                    'lowest_fr_least_familiar_word': [debug_info_tuple_double(field_metrics.lowest_fr_least_familiar_word) for field_metrics in note_metrics],
                    'lowest_fr_word': [debug_info_tuple_single(field_metrics.lowest_fr_word) for field_metrics in note_metrics],
                }
                if set_lexical_underexposure:
                    debug_info['ue_scores'] = [debug_info_float(field_metrics.ue_score) for field_metrics in note_metrics]
                    debug_info['highest_ue_word'] = [debug_info_tuple_single(field_metrics.highest_ue_word) for field_metrics in note_metrics]
                if set_familiarity_sweetspot:
                    debug_info['familiarity_sweetspot_scores'] = [debug_info_float(field_metrics.familiarity_sweetspot_score) for field_metrics in note_metrics]
                if set_ideal_new_word_count:
                    debug_info['ideal_new_words_count_scores'] = [debug_info_float(field_metrics.ideal_new_words_count_score) for field_metrics in note_metrics]
                if set_proper_introduction:
                    debug_info['proper_introduction_scores'] = [debug_info_float(field_metrics.proper_introduction_score) for field_metrics in note_metrics]
                if set_proper_introduction_dispersed:
                    debug_info['proper_introduction_dispersed_scores'] = [debug_info_float(field_metrics.proper_introduction_dispersed_score) for field_metrics in note_metrics]

                fm_debug_info_pieces: list[str] = [target_title_html]
                for info_name, info_val in debug_info.items():
                    if info_val:
                        fields_info = " | ".join(field_info for field_info in info_val)
                        fm_debug_info_pieces.append(f"{info_name}: {fields_info}<br />\n")
                note_data['fm_debug_info'] = "".join(fm_debug_info_pieces)

            # set fm_debug_ranking_info
            if 'fm_debug_ranking_info' in note:
                if note.id in notes_new_card:
                    if not note.id in reorder_scope_notes_ids:
                        note_data['fm_debug_ranking_info'] = debug_info_not_in_reorder_scope
                    else:
                        fm_debug_ranking_info_pieces: list[str] = [target_title_html]
                        used_ranking_factors = {k: v for k, v in notes_ranking_scores.items() if k in self.ranking_factors_span and self.ranking_factors_span[k] > 0}
                        ranking_scores = dict(sorted(used_ranking_factors.items(), key=lambda item: (item[1][note.id]*self.ranking_factors_span[item[0]]), reverse=True))
                        for factor_name, factor_values in ranking_scores.items():
                            factor_value = factor_values[note.id]
                            factor_span = self.ranking_factors_span[factor_name]
                            factor_score = factor_value*factor_span
                            fm_debug_ranking_info_pieces.append("{}: {:.3f} <span style=\"opacity:0.5;\">x {} = {:.3f}</span><br />\n".format(factor_name, factor_value, factor_span, factor_score))
                        note_data['fm_debug_ranking_info'] = "".join(fm_debug_ranking_info_pieces)
                else:
                    note_data['fm_debug_ranking_info'] = debug_info_no_new_cards

            # set fm_debug_words_info
            if 'fm_debug_words_info' in note:

                fields_words_ue_scores_sorted = []
                fields_words_fr_scores_sorted = []
                fields_words_familiarity_sweetspot_scores_sorted = []
                fields_words_familiarity_scores_sorted = []

                for field_metrics in note_metrics:
                    fields_words_ue_scores_sorted.append(
                        dict(sorted(field_metrics.words_ue_scores.items(), key=lambda item: item[1], reverse=True))
                    )
                    fields_words_fr_scores_sorted.append(
                        dict(sorted(field_metrics.words_fr_scores.items(), key=lambda item: item[1], reverse=True))
                    )
                    fields_words_familiarity_sweetspot_scores_sorted.append(
                        dict(sorted(field_metrics.words_familiarity_sweetspot_scores.items(), key=lambda item: item[1], reverse=True))
                    )
                    fields_words_familiarity_scores_sorted.append(
                        dict(sorted(field_metrics.words_familiarity_scores.items(), key=lambda item: item[1], reverse=True))
                    )

                note_data['fm_debug_words_info'] = (
                    f"{target_title_html}"
                    f"words_ue_scores: {debug_info_list_dict(fields_words_ue_scores_sorted)}<br />\n"
                    f"words_fr_scores: {debug_info_list_dict(fields_words_fr_scores_sorted)}<br />\n"
                    f"familiarity_sweetspot_scores: {debug_info_list_dict(fields_words_familiarity_sweetspot_scores_sorted)}<br />\n"
                    f"familiarity_scores: {debug_info_list_dict(fields_words_familiarity_scores_sorted)}<br />\n"
                )

            notes_debug_info[note_id] = note_data

        return notes_debug_info
