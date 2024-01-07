"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from math import fsum
from statistics import fmean, mean, median
from typing import Iterable, NewType, Type, TypedDict, Union

from anki.collection import Collection
from anki.cards import CardId, Card
from anki.notes import NoteId

from .target_cards import TargetCard, TargetCards
from .language_data import LangId, LangDataId, LanguageData
from .lib.utilities import *
from .text_processing import TextProcessing, WordToken


# This is used to make the corpus data per field.
# It is created by using model.id and note field name.
# It could be changed to make it per LangId (thus merging multiple note field
# when they have to same LangId)
CorpusId = NewType('CorpusId', str)


@dataclass(frozen=True)
class TargetNoteFieldContentData:
    corpus_id: CorpusId
    field_name: str
    field_value_plain_text: str
    field_value_tokenized: list[WordToken]
    target_language_key: LangDataId
    target_language_id: LangId


@dataclass
class TargetReviewedContentMetrics:
    words: dict[WordToken, list[TargetCard]] = field(default_factory=dict)
    words_presence: dict[WordToken, list[float]] = field(default_factory=dict)  # list because a word can occur multiple times in a field
    words_presence_card_score: dict[WordToken, list[float]] = field(default_factory=dict)
    words_familiarity: dict[WordToken, float] = field(default_factory=dict)
    words_familiarity_mean: float = field(default=0.0)
    words_familiarity_median: float = field(default=0.0)
    words_familiarity_positional: dict[WordToken, float] = field(default_factory=dict)
    words_familiarity_sweetspot: dict[WordToken, float] = field(default_factory=dict)


@dataclass
class TargetContentMetrics:
    words_lexical_discrepancy: dict[WordToken, float] = field(default_factory=dict)
    reviewed: TargetReviewedContentMetrics = field(default_factory=TargetReviewedContentMetrics)


class TargetCorpusData:
    """
    Class representing corpus data from target cards.
    """

    target_cards: TargetCards
    field_data_per_card_note: dict[NoteId, list[TargetNoteFieldContentData]]
    content_metrics: dict[CorpusId, TargetContentMetrics]
    familiarity_sweetspot_point: float

    def __init__(self):

        self.field_data_per_card_note = {}
        self.content_metrics = defaultdict(TargetContentMetrics)
        self.familiarity_sweetspot_point = 0.75

    def create_data(self, target_cards: TargetCards, target_fields_by_notes_name: dict[str, dict[str, str]], language_data: LanguageData) -> None:
        """
        Create corpus data for the given target and its cards.
        """

        if len(target_cards) == 0:
            return

        self.target_cards = target_cards

        for card in target_cards.all_cards:

            if card.nid not in self.field_data_per_card_note:

                card_note = target_cards.get_note(card.nid)
                card_note_type = target_cards.get_model(card_note.mid)

                if (card_note_type is None):
                    raise Exception("Card note type not found for card.nid '{}'!".format(card_note.mid))
                if card_note_type['name'] not in target_fields_by_notes_name:  # note type name is not defined as target
                    continue

                target_note_fields = target_fields_by_notes_name[card_note_type['name']]

                card_note_fields_in_target: list[TargetNoteFieldContentData] = []
                for field_name, field_val in card_note.items():
                    if field_name in target_note_fields.keys():

                        corpus_id = str(card_note_type['id'])+" => "+field_name

                        lang_key = target_note_fields[field_name].lower()
                        lang_id = lang_key
                        if (len(lang_id) > 3 and lang_id[2] == '_'):
                            lang_id = lang_id[:2]

                        plain_text = TextProcessing.get_plain_text(field_val).lower()
                        field_value_tokenized = TextProcessing.get_word_tokens_from_text(plain_text, lang_id)

                        card_note_fields_in_target.append(TargetNoteFieldContentData(
                            corpus_id=CorpusId(corpus_id),
                            field_name=field_name,
                            field_value_plain_text=plain_text,
                            field_value_tokenized=field_value_tokenized,
                            target_language_key=LangDataId(lang_key),
                            target_language_id=LangId(lang_id)
                        ))

                self.field_data_per_card_note[card.nid] = card_note_fields_in_target

        self.__set_notes_reviewed_words()
        self.__set_notes_reviewed_words_presence()
        self.__set_notes_reviewed_words_familiarity()
        self.__set_notes_reviewed_words_familiarity_sweetspot()
        self.__set_notes_lexical_discrepancy(language_data)

    def __get_reviewed_words_card_memorized_scores(self) -> dict[CardId, float]:

        cards_interval: list[float] = []
        cards_reps: list[float] = []
        cards_ease: list[float] = []

        for card in self.target_cards.reviewed_cards:
            cards_interval.append(card.ivl)
            cards_reps.append(card.reps)
            cards_ease.append(card.factor)

        # smooth out top values

        for metric_list, turnover_val in ((cards_interval, 30*7), (cards_reps, 14)):
            for index in range(len(metric_list)):
                if metric_list[index] > turnover_val:
                    metric_list[index] = mean([turnover_val, metric_list[index]])

        # get scores

        card_memorized_scores: dict[CardId, float] = {}

        cards_interval_max = max(cards_interval)
        cards_reps_max = max(cards_reps)
        cards_ease_max = max(cards_ease)

        for card in self.target_cards.reviewed_cards:
            card_memorized_scores[card.id] = fmean([(card.ivl/cards_interval_max), (card.reps/cards_reps_max), (card.factor/cards_ease_max)])

        card_memorized_scores = normalize_dict_floats_values(card_memorized_scores)
        card_memorized_scores = sort_dict_floats_values(card_memorized_scores)

        return card_memorized_scores

    def __set_notes_reviewed_words(self) -> None:

        for card in self.target_cards.reviewed_cards:

            for field_data in self.field_data_per_card_note[card.nid]:

                corpus_key = field_data.corpus_id

                for word_token in field_data.field_value_tokenized:
                    if word_token not in self.content_metrics[corpus_key].reviewed.words:
                        self.content_metrics[corpus_key].reviewed.words[word_token] = []
                    self.content_metrics[corpus_key].reviewed.words[word_token].append(card)

    @staticmethod
    def __calc_word_presence_score(word_token: str, context_num_chars: int, context_num_tokens: int, position_index: int) -> float:

        presence_num_chars = len(word_token)/context_num_chars
        presence_num_tokens = 1/context_num_tokens
        position_value = 1/(position_index+1)
        return (presence_num_chars+presence_num_tokens+position_value)/3

    def __set_notes_reviewed_words_presence(self) -> None:

        card_memorized_scores = self.__get_reviewed_words_card_memorized_scores()

        for card in self.target_cards.reviewed_cards:

            for field_data in self.field_data_per_card_note[card.nid]:

                corpus_key = field_data.corpus_id
                field_num_tokens = len(field_data.field_value_tokenized)
                field_num_chars_tokens = len(''.join(field_data.field_value_tokenized))

                for index, word_token in enumerate(field_data.field_value_tokenized):

                    if word_token not in self.content_metrics[corpus_key].reviewed.words_presence:
                        self.content_metrics[corpus_key].reviewed.words_presence[word_token] = []
                        self.content_metrics[corpus_key].reviewed.words_presence_card_score[word_token] = []

                    word_presence_score = self.__calc_word_presence_score(word_token, field_num_chars_tokens, field_num_tokens, index)
                    self.content_metrics[corpus_key].reviewed.words_presence[word_token].append(word_presence_score)
                    self.content_metrics[corpus_key].reviewed.words_presence_card_score[word_token].append(card_memorized_scores[card.id])

    def __set_notes_reviewed_words_familiarity(self) -> None:
        """
        Set the familiarity score for each word per field of card note, based on word presence in reviewed cards and score of card.
        """
        for corpus_key in self.content_metrics.keys():

            field_familiarity_scores_per_word: list[float] = []

            for word_token, word_presence_scores in self.content_metrics[corpus_key].reviewed.words_presence.items():
                word_presence_card_scores = self.content_metrics[corpus_key].reviewed.words_presence_card_score[word_token]
                field_familiarity_scores_per_word.append(fsum(word_presence_scores)+fsum(word_presence_card_scores))

            field_avg_word_familiarity_score = fmean(field_familiarity_scores_per_word)

            for index, word_token in enumerate(self.content_metrics[corpus_key].reviewed.words_presence.keys()):

                word_familiarity_smooth_score = field_familiarity_scores_per_word[index]

                if (word_familiarity_smooth_score > field_avg_word_familiarity_score*16):
                    word_familiarity_smooth_score = fmean([word_familiarity_smooth_score] + [field_avg_word_familiarity_score]*4)
                if (word_familiarity_smooth_score > field_avg_word_familiarity_score*8):
                    word_familiarity_smooth_score = fmean([word_familiarity_smooth_score] + [field_avg_word_familiarity_score]*2)
                if (word_familiarity_smooth_score > field_avg_word_familiarity_score):
                    word_familiarity_smooth_score = fmean([word_familiarity_smooth_score, field_avg_word_familiarity_score])

                self.content_metrics[corpus_key].reviewed.words_familiarity[word_token] = word_familiarity_smooth_score

            # make scores values relative

            self.content_metrics[corpus_key].reviewed.words_familiarity = normalize_dict_floats_values(self.content_metrics[corpus_key].reviewed.words_familiarity)
            self.content_metrics[corpus_key].reviewed.words_familiarity = sort_dict_floats_values(self.content_metrics[corpus_key].reviewed.words_familiarity)

            # set avg and median

            self.content_metrics[corpus_key].reviewed.words_familiarity_mean = mean(self.content_metrics[corpus_key].reviewed.words_familiarity.values())
            self.content_metrics[corpus_key].reviewed.words_familiarity_median = median(self.content_metrics[corpus_key].reviewed.words_familiarity.values())

            # also relative, but based on (sorted) position, just like value received from WordFrequencyList.get_word_frequency

            max_rank = len(self.content_metrics[corpus_key].reviewed.words_familiarity)

            for index, word_token in enumerate(self.content_metrics[corpus_key].reviewed.words_familiarity.keys()):
                familiarity_positional = (max_rank-(index))/max_rank
                self.content_metrics[corpus_key].reviewed.words_familiarity_positional[word_token] = familiarity_positional

    def __set_notes_reviewed_words_familiarity_sweetspot(self) -> None:

        for corpus_key in self.content_metrics.keys():

            median_familiarity = median(self.content_metrics[corpus_key].reviewed.words_familiarity.values())

            for word_token in self.content_metrics[corpus_key].reviewed.words_familiarity:

                familiarity = self.content_metrics[corpus_key].reviewed.words_familiarity[word_token]
                familiarity_sweetspot_value = median_familiarity*self.familiarity_sweetspot_point

                if (familiarity > familiarity_sweetspot_value*2.6666):
                    continue

                familiarity_sweetspot_rating = 1-abs(familiarity-familiarity_sweetspot_value)

                self.content_metrics[corpus_key].reviewed.words_familiarity_sweetspot[word_token] = familiarity_sweetspot_rating

            self.content_metrics[corpus_key].reviewed.words_familiarity_sweetspot = normalize_dict_floats_values(self.content_metrics[corpus_key].reviewed.words_familiarity_sweetspot)
            self.content_metrics[corpus_key].reviewed.words_familiarity_sweetspot = sort_dict_floats_values(self.content_metrics[corpus_key].reviewed.words_familiarity_sweetspot)

    def __set_notes_lexical_discrepancy(self, language_data: LanguageData) -> None:

        for note_fields in self.field_data_per_card_note.values():

            for field in note_fields:

                corpus_key = field.corpus_id
                language_key = field.target_language_key

                for word_token in field.field_value_tokenized:

                    word_fr = language_data.get_word_frequency(language_key, word_token, 0)
                    word_familiarity = self.content_metrics[corpus_key].reviewed.words_familiarity_positional.get(word_token, 0)
                    word_lexical_discrepancy_rating = (word_fr - word_familiarity)
                    if (word_lexical_discrepancy_rating >= 0):
                        self.content_metrics[corpus_key].words_lexical_discrepancy[word_token] = word_lexical_discrepancy_rating

        for corpus_key in self.content_metrics.keys():
            self.content_metrics[corpus_key].words_lexical_discrepancy = normalize_dict_floats_values(self.content_metrics[corpus_key].words_lexical_discrepancy)
            self.content_metrics[corpus_key].words_lexical_discrepancy = sort_dict_floats_values(self.content_metrics[corpus_key].words_lexical_discrepancy)
