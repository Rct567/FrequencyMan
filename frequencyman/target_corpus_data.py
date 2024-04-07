"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from math import fsum
from statistics import fmean, median
from typing import NewType
from enum import Enum

from anki.cards import CardId, Card
from anki.notes import NoteId

from .target_cards import TargetCard, TargetCards
from .language_data import LangId, LangDataId, LanguageData
from .lib.utilities import *
from .text_processing import TextProcessing, WordToken


class CorpusSegmentationStrategy(Enum):
    BY_NOTE_MODEL_ID_AND_FIELD_NAME = 1
    BY_LANG_DATA_ID = 2
    BY_LANG_ID = 3

CorpusSegmentId = NewType('CorpusSegmentId', str)


@dataclass(frozen=True)
class TargetNoteFieldContentData:
    corpus_segment_id: CorpusSegmentId
    field_name: str
    field_value_tokenized: list[WordToken]
    target_language_data_id: LangDataId
    target_language_id: LangId


@dataclass
class TargetReviewedContentMetrics:
    words: dict[WordToken, list[TargetCard]] = field(default_factory=dict)
    words_presence: dict[WordToken, list[float]] = field(default_factory=dict)  # list because a word can occur multiple times in a field
    words_cards_familiarity_factor: dict[WordToken, list[float]] = field(default_factory=dict)
    words_familiarity: dict[WordToken, float] = field(default_factory=dict)
    words_familiarity_mean: float = field(default=0.0)
    words_familiarity_median: float = field(default=0.0)
    words_familiarity_positional: dict[WordToken, float] = field(default_factory=dict)
    words_familiarity_sweetspot: dict[WordToken, float] = field(default_factory=dict)


@dataclass
class TargetContentMetrics:
    word_frequency: dict[WordToken, float] = field(default_factory=dict)
    words_underexposure: dict[WordToken, float] = field(default_factory=dict)
    reviewed: TargetReviewedContentMetrics = field(default_factory=TargetReviewedContentMetrics)


class TargetCorpusData:
    """
    Class representing corpus data from target cards.
    """

    target_cards: TargetCards
    field_data_per_card_note: dict[NoteId, list[TargetNoteFieldContentData]]
    content_metrics: dict[CorpusSegmentId, TargetContentMetrics]
    familiarity_sweetspot_point: float
    suspended_card_value: float
    suspended_leech_card_value: float
    segmentation_strategy: CorpusSegmentationStrategy

    def __init__(self):

        self.field_data_per_card_note = {}
        self.content_metrics = defaultdict(TargetContentMetrics)
        self.familiarity_sweetspot_point = 0.45
        self.suspended_card_value = 0.5
        self.suspended_leech_card_value = 0.0
        self.segmentation_strategy = CorpusSegmentationStrategy.BY_LANG_DATA_ID

    def create_data(self, target_cards: TargetCards, target_fields_per_note_type: dict[str, dict[str, LangDataId]], language_data: LanguageData) -> None:
        """
        Create corpus data for the given target and its cards.
        """

        if len(target_cards) == 0:
            return

        if len(self.content_metrics) > 0:
            raise Exception("Data already created by TargetCorpusData.")

        self.target_cards = target_cards

        for card in target_cards.all_cards:

            if card.nid not in self.field_data_per_card_note:

                card_note = target_cards.get_note(card.nid)
                card_note_type = target_cards.get_model(card_note.mid)

                if (card_note_type is None):
                    raise Exception("Card note type not found for card.nid '{}'!".format(card_note.mid))
                if card_note_type['name'] not in target_fields_per_note_type:  # note type name is not defined as target
                    continue

                target_note_fields = target_fields_per_note_type[card_note_type['name']]

                card_note_fields_in_target: list[TargetNoteFieldContentData] = []
                for field_name, field_val in card_note.items():
                    if field_name in target_note_fields.keys():

                        lang_data_id = target_note_fields[field_name]
                        lang_id = LanguageData.get_lang_id_from_data_id(lang_data_id)

                        if self.segmentation_strategy == CorpusSegmentationStrategy.BY_LANG_DATA_ID:
                            corpus_segment_id = str(lang_data_id)
                        elif self.segmentation_strategy == CorpusSegmentationStrategy.BY_LANG_ID:
                            corpus_segment_id = str(lang_id)
                        elif self.segmentation_strategy == CorpusSegmentationStrategy.BY_NOTE_MODEL_ID_AND_FIELD_NAME:
                            corpus_segment_id = str(card_note_type['id'])+" => "+field_name
                        else:
                            raise Exception("Invalid segmentation_strategy set!")

                        plain_text = TextProcessing.get_plain_text(field_val)
                        field_value_tokenized = TextProcessing.get_word_tokens_from_text(plain_text, lang_id)

                        card_note_fields_in_target.append(TargetNoteFieldContentData(
                            corpus_segment_id=CorpusSegmentId(corpus_segment_id),
                            field_name=field_name,
                            field_value_tokenized=field_value_tokenized,
                            target_language_data_id=lang_data_id,
                            target_language_id=lang_id
                        ))

                self.field_data_per_card_note[card.nid] = card_note_fields_in_target

        self.__set_word_frequency(language_data)
        self.__set_notes_reviewed_words()
        self.__set_notes_reviewed_words_presence()
        self.__set_notes_reviewed_words_familiarity()
        self.__set_notes_reviewed_words_familiarity_sweetspot()
        self.__set_notes_words_underexposure()

    def __set_word_frequency(self, language_data: LanguageData):

        for note_id in self.target_cards.get_notes().keys():

            for field_data in self.field_data_per_card_note[note_id]:

                corpus_segment_id = field_data.corpus_segment_id
                lang_data_id = field_data.target_language_data_id

                for word_token in field_data.field_value_tokenized:
                    word_frequency = language_data.get_word_frequency(lang_data_id, word_token, 0)
                    if word_frequency > 0:
                        self.content_metrics[corpus_segment_id].word_frequency[word_token] = word_frequency

        for corpus_segment_id in self.content_metrics.keys():
            if self.content_metrics[corpus_segment_id].word_frequency:
                self.content_metrics[corpus_segment_id].word_frequency = sort_dict_floats_values(self.content_metrics[corpus_segment_id].word_frequency)
                self.content_metrics[corpus_segment_id].word_frequency = normalize_positional_dict_floats_values(self.content_metrics[corpus_segment_id].word_frequency)

    @staticmethod
    def __get_cards_familiarity_score(cards: list[TargetCard]) -> dict[CardId, float]:

        if not cards:
            return {}

        cards_interval: list[float] = []
        cards_reps: list[float] = []
        cards_ease: list[float] = []

        for card in cards:
            cards_interval.append(card.ivl)
            cards_reps.append(card.reps)
            cards_ease.append(card.factor)

        # smooth out top values

        for metric_list, turnover_val in ((cards_interval, 30*7), (cards_reps, 14)):
            for index in range(len(metric_list)):
                if metric_list[index] > turnover_val:
                    metric_list[index] = (turnover_val + metric_list[index]) / 2

        # get scores

        cards_familiarity: dict[CardId, float] = {}

        cards_interval_max = max(cards_interval)
        cards_reps_max = max(cards_reps)
        cards_ease_max = max(cards_ease)

        for card in cards:
            card_score = ((card.ivl/cards_interval_max) + ((card.reps/cards_reps_max)/4) + (card.factor/cards_ease_max)) / 2.25
            cards_familiarity[card.id] = card_score

        # done

        return cards_familiarity

    @staticmethod
    def __get_cards_familiarity_factors(cards: list[TargetCard], suspended_card_value: float, suspended_leech_card_value: float) -> dict[CardId, float]:

        cards_familiarity_value = TargetCorpusData.__get_cards_familiarity_score(cards)

        for card in cards:
            if card.queue == -1:  # suspended card
                if card.is_leech:
                    cards_familiarity_value[card.id] = cards_familiarity_value[card.id]*suspended_leech_card_value
                else:
                    cards_familiarity_value[card.id] = cards_familiarity_value[card.id]*suspended_card_value

        # devalue cards from same note (devalue subsequently more as more cards from same note are found)

        cards_familiarity_value = sort_dict_floats_values(cards_familiarity_value)

        note_count: dict[NoteId, int] = {}
        cards_note_ids: dict[CardId, NoteId] = {card.id: card.nid for card in cards}

        for card_id in cards_familiarity_value.keys():

            note_id = cards_note_ids[card_id]

            if note_id not in note_count:
                note_count[note_id] = 1
            else:
                note_count[note_id] += 1
                devalue_factor = (1+note_count[note_id])/2
                cards_familiarity_value[card_id] = cards_familiarity_value[card_id]/devalue_factor

        # normalize

        cards_familiarity_value = normalize_dict_floats_values(cards_familiarity_value)

        return cards_familiarity_value

    def __set_notes_reviewed_words(self) -> None:

        for card in self.target_cards.reviewed_cards:

            for field_data in self.field_data_per_card_note[card.nid]:

                corpus_segment_id = field_data.corpus_segment_id

                for word_token in field_data.field_value_tokenized:
                    if word_token not in self.content_metrics[corpus_segment_id].reviewed.words:
                        self.content_metrics[corpus_segment_id].reviewed.words[word_token] = []
                    self.content_metrics[corpus_segment_id].reviewed.words[word_token].append(card)

    @staticmethod
    def __calc_word_presence_score(word_token: str, context_num_chars: int, context_num_tokens: int, position_index: int) -> float:

        presence_num_chars = len(word_token)/context_num_chars
        presence_num_tokens = 1/context_num_tokens
        position_value = 1/(position_index+1)
        return (presence_num_chars+presence_num_tokens+position_value)/3

    def __set_notes_reviewed_words_presence(self) -> None:

        cards_familiarity_factor = self.__get_cards_familiarity_factors(self.target_cards.reviewed_cards, self.suspended_card_value, self.suspended_leech_card_value)

        for card in self.target_cards.reviewed_cards:

            for field_data in self.field_data_per_card_note[card.nid]:

                corpus_segment_id = field_data.corpus_segment_id
                field_num_tokens = len(field_data.field_value_tokenized)
                field_num_chars_tokens = len(''.join(field_data.field_value_tokenized))

                for index, word_token in enumerate(field_data.field_value_tokenized):

                    if word_token not in self.content_metrics[corpus_segment_id].reviewed.words_presence:
                        self.content_metrics[corpus_segment_id].reviewed.words_presence[word_token] = []
                        self.content_metrics[corpus_segment_id].reviewed.words_cards_familiarity_factor[word_token] = []

                    word_presence_score = self.__calc_word_presence_score(word_token, field_num_chars_tokens, field_num_tokens, index)
                    self.content_metrics[corpus_segment_id].reviewed.words_presence[word_token].append(word_presence_score)
                    self.content_metrics[corpus_segment_id].reviewed.words_cards_familiarity_factor[word_token].append(cards_familiarity_factor[card.id])
                    assert word_presence_score <= 1 and cards_familiarity_factor[card.id] <= 1

    def __set_notes_reviewed_words_familiarity(self) -> None:

        for corpus_segment_id in self.content_metrics.keys():

            for word_token, word_presence_scores in self.content_metrics[corpus_segment_id].reviewed.words_presence.items():
                cards_familiarity_factor = self.content_metrics[corpus_segment_id].reviewed.words_cards_familiarity_factor[word_token]
                words_familiarity = fsum(word_presence*((1+card_familiarity_factor)**2.5) for word_presence, card_familiarity_factor in zip(word_presence_scores, cards_familiarity_factor))
                self.content_metrics[corpus_segment_id].reviewed.words_familiarity[word_token] = words_familiarity

            # smooth out top values

            if not self.content_metrics[corpus_segment_id].reviewed.words_familiarity:
                continue

            field_avg_word_familiarity_score = fmean(self.content_metrics[corpus_segment_id].reviewed.words_familiarity.values())

            for word_token, words_familiarity in self.content_metrics[corpus_segment_id].reviewed.words_familiarity.items():

                word_familiarity_smooth_score = words_familiarity

                if (word_familiarity_smooth_score > field_avg_word_familiarity_score*16):
                    word_familiarity_smooth_score = (word_familiarity_smooth_score + (field_avg_word_familiarity_score*4)) / 5
                if (word_familiarity_smooth_score > field_avg_word_familiarity_score*8):
                    word_familiarity_smooth_score = (word_familiarity_smooth_score + (field_avg_word_familiarity_score*2)) / 3
                if (word_familiarity_smooth_score > field_avg_word_familiarity_score):
                    word_familiarity_smooth_score = (word_familiarity_smooth_score + field_avg_word_familiarity_score) / 2

                self.content_metrics[corpus_segment_id].reviewed.words_familiarity[word_token] = word_familiarity_smooth_score

            # make scores values relative

            self.content_metrics[corpus_segment_id].reviewed.words_familiarity = normalize_dict_floats_values(self.content_metrics[corpus_segment_id].reviewed.words_familiarity)
            self.content_metrics[corpus_segment_id].reviewed.words_familiarity = sort_dict_floats_values(self.content_metrics[corpus_segment_id].reviewed.words_familiarity)

            # set avg and median

            self.content_metrics[corpus_segment_id].reviewed.words_familiarity_mean = fmean(self.content_metrics[corpus_segment_id].reviewed.words_familiarity.values())
            self.content_metrics[corpus_segment_id].reviewed.words_familiarity_median = median(self.content_metrics[corpus_segment_id].reviewed.words_familiarity.values())

            # also relative, but based on (sorted) position, just like word_frequency

            self.content_metrics[corpus_segment_id].reviewed.words_familiarity_positional = normalize_positional_dict_floats_values(self.content_metrics[corpus_segment_id].reviewed.words_familiarity)

    def __set_notes_reviewed_words_familiarity_sweetspot(self) -> None:

        for corpus_segment_id in self.content_metrics.keys():

            median_familiarity = self.content_metrics[corpus_segment_id].reviewed.words_familiarity_median

            for word_token in self.content_metrics[corpus_segment_id].reviewed.words_familiarity:

                familiarity = self.content_metrics[corpus_segment_id].reviewed.words_familiarity[word_token]
                familiarity_sweetspot_value = median_familiarity*self.familiarity_sweetspot_point

                familiarity_sweetspot_rating = (1-abs(familiarity-familiarity_sweetspot_value))

                self.content_metrics[corpus_segment_id].reviewed.words_familiarity_sweetspot[word_token] = familiarity_sweetspot_rating

            # sort
            self.content_metrics[corpus_segment_id].reviewed.words_familiarity_sweetspot = sort_dict_floats_values(self.content_metrics[corpus_segment_id].reviewed.words_familiarity_sweetspot)

            # cut of bottom 10%
            num_to_keep = int(len(self.content_metrics[corpus_segment_id].reviewed.words_familiarity_sweetspot) * 0.9)
            if num_to_keep > 100:
                self.content_metrics[corpus_segment_id].reviewed.words_familiarity_sweetspot = dict(
                    list(self.content_metrics[corpus_segment_id].reviewed.words_familiarity_sweetspot.items())[:num_to_keep])

            # normalize
            self.content_metrics[corpus_segment_id].reviewed.words_familiarity_sweetspot = normalize_dict_floats_values(self.content_metrics[corpus_segment_id].reviewed.words_familiarity_sweetspot)

    def __set_notes_words_underexposure(self) -> None:

        for note_fields in self.field_data_per_card_note.values():

            for field in note_fields:

                corpus_segment_id = field.corpus_segment_id

                for word_token in field.field_value_tokenized:

                    word_fr = self.content_metrics[corpus_segment_id].word_frequency.get(word_token, 0)

                    if word_fr == 0:
                        continue

                    word_familiarity = self.content_metrics[corpus_segment_id].reviewed.words_familiarity_positional.get(word_token, 0)
                    word_underexposure_rating = (word_fr - word_familiarity)

                    if (word_underexposure_rating > 0):
                        word_underexposure_rating = word_underexposure_rating * ((1 + word_familiarity) ** 1.5)
                        if word_familiarity == 0:
                            word_underexposure_rating = word_underexposure_rating*0.75
                        self.content_metrics[corpus_segment_id].words_underexposure[word_token] = word_underexposure_rating

        for corpus_segment_id in self.content_metrics.keys():

            # sort
            self.content_metrics[corpus_segment_id].words_underexposure = sort_dict_floats_values(self.content_metrics[corpus_segment_id].words_underexposure)

            # cut of bottom 10%
            num_to_keep = int(len(self.content_metrics[corpus_segment_id].words_underexposure) * 0.9)
            if num_to_keep > 100:
                self.content_metrics[corpus_segment_id].words_underexposure = dict(list(self.content_metrics[corpus_segment_id].words_underexposure.items())[:num_to_keep])

            # normalize
            self.content_metrics[corpus_segment_id].words_underexposure = normalize_dict_floats_values(self.content_metrics[corpus_segment_id].words_underexposure)
