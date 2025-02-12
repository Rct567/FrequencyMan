"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from functools import cached_property
from math import fsum
from statistics import fmean, median
from typing import NewType, Sequence, Union
from enum import Enum

from anki.cards import CardId, Card
from anki.notes import NoteId

from .lib.persistent_cacher import PersistentCacher
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
class NoteFieldContentData:
    corpus_segment_id: CorpusSegmentId
    field_name: str
    field_value: str
    target_language_data_id: LangDataId
    target_language_id: LangId
    cacher: PersistentCacher

    @cached_property
    def field_value_tokenized(self) -> list[WordToken]:

        if self.field_value == "":
            field_value_tokenized = []
        else:
            cache_key = str(self.target_language_id)+self.field_value
            field_value_tokenized = self.cacher.get_item(cache_key, lambda: TextProcessing.get_word_tokens_from_text(TextProcessing.get_plain_text(self.field_value), self.target_language_id))

        return field_value_tokenized


@dataclass
class SegmentContentMetrics:

    lang_id: LangId
    lang_data_id: LangDataId
    focus_words_max_familiarity: float
    familiarity_sweetspot_point: Union[float, str]
    target_cards: TargetCards
    language_data: LanguageData
    cards_familiarity_factor: dict[CardId, float]

    targeted_fields_per_note: dict[NoteId, list[NoteFieldContentData]] = field(default_factory=lambda: defaultdict(list))

    @cached_property
    def mature_words(self) -> set[WordToken]:

        mature_words: set[WordToken] = set()

        for word_token, word_familiarity in self.words_familiarity.items():

            if word_familiarity > self.focus_words_max_familiarity:
                mature_words.add(word_token)

        return mature_words

    @cached_property
    def words_underexposure(self) -> dict[WordToken, float]:

        words_underexposure: dict[WordToken, float] = {}

        for word_token, word_fr in self.word_frequency.items():

            assert word_fr > 0
            word_familiarity = self.words_familiarity_positional.get(word_token, 0)
            word_underexposure_rating = (word_fr ** 3) - (word_familiarity ** 3)

            if (word_underexposure_rating > 0):
                if self.words_familiarity.get(word_token, 0) < 1.9:
                    word_underexposure_rating = word_underexposure_rating * ((1 + word_familiarity) ** 1.5)
                if word_familiarity == 0:
                    word_underexposure_rating = word_underexposure_rating*0.75
                words_underexposure[word_token] = word_underexposure_rating

        words_underexposure = sort_dict_floats_values(words_underexposure)
        words_underexposure = remove_bottom_percent_dict(words_underexposure, 0.1, 100)
        words_underexposure = normalize_dict_floats_values(words_underexposure)
        return words_underexposure

    @cached_property
    def words_familiarity_sweetspot(self) -> dict[WordToken, float]:

        if not self.words_familiarity:
            return {}

        words_familiarity_sweetspot: dict[WordToken, float] = {}

        if isinstance(self.familiarity_sweetspot_point, str):
            if self.familiarity_sweetspot_point[0] == '^':
                median_familiarity = self.words_familiarity_median
                familiarity_sweetspot_point = median_familiarity*float(self.familiarity_sweetspot_point[1:])
            elif self.familiarity_sweetspot_point[0] == '~':
                familiarity_sweetspot_point = self.focus_words_max_familiarity*float(self.familiarity_sweetspot_point[1:])
            else:
                raise ValueError("Invalid value for familiarity_sweetspot_point!")
        else:
            familiarity_sweetspot_point = self.familiarity_sweetspot_point

        if not self.words_familiarity_max > (familiarity_sweetspot_point*2):
            return {}

        for word_token in self.words_familiarity:

            familiarity = self.words_familiarity[word_token]
            familiarity_sweetspot_rating = (self.words_familiarity_max-abs(familiarity-familiarity_sweetspot_point))

            words_familiarity_sweetspot[word_token] = familiarity_sweetspot_rating

        words_familiarity_sweetspot = sort_dict_floats_values(words_familiarity_sweetspot)
        words_familiarity_sweetspot = remove_bottom_percent_dict(words_familiarity_sweetspot, 0.1, 100)
        words_familiarity_sweetspot = normalize_dict_floats_values(words_familiarity_sweetspot)
        return words_familiarity_sweetspot

    @cached_property
    def words_familiarity(self) -> dict[WordToken, float]:

        words_familiarity: dict[WordToken, float] = {}

        for word_token, word_presence_scores in self.reviewed_words_presence.items():
            cards_familiarity_factor = self.reviewed_words_cards_familiarity_factor[word_token]
            assert len(word_presence_scores) == len(cards_familiarity_factor)
            word_familiarity = fsum((card_familiarity_factor * word_presence) for word_presence, card_familiarity_factor in zip(word_presence_scores, cards_familiarity_factor))
            words_familiarity[word_token] = word_familiarity

        return sort_dict_floats_values(words_familiarity)

    @cached_property
    def words_familiarity_mean(self) -> float:

        words_familiarity_values = self.words_familiarity.values()
        if not words_familiarity_values:
            return 0

        return fmean(words_familiarity_values)

    @cached_property
    def words_familiarity_median(self) -> float:

        words_familiarity_values = self.words_familiarity.values()
        if not words_familiarity_values:
            return 0

        return median(self.words_familiarity.values())

    @cached_property
    def words_familiarity_max(self) -> float:

        words_familiarity_values = self.words_familiarity.values()
        if not words_familiarity_values:
            return 0

        return max(words_familiarity_values)

    @cached_property
    def words_familiarity_positional(self) -> dict[WordToken, float]:

        return normalize_dict_positional_floats_values(self.words_familiarity)

    @cached_property
    def reviewed_words_presence(self) -> dict[WordToken, list[float]]:

        reviewed_words_presence: dict[WordToken, list[float]] = {}

        for card in self.target_cards.reviewed_cards:

            for field_data in self.targeted_fields_per_note[card.nid]:

                for index, word_token in enumerate(field_data.field_value_tokenized):

                    if word_token not in reviewed_words_presence:
                        reviewed_words_presence[word_token] = []

                    word_presence_score = TextProcessing.calc_word_presence_score(word_token, field_data.field_value_tokenized, index)
                    reviewed_words_presence[word_token].append(word_presence_score)

        return reviewed_words_presence

    @cached_property
    def all_words_presence(self) -> dict[WordToken, list[float]]:

        words_presence: dict[WordToken, list[float]] = {}

        for card in self.target_cards.all_cards:

            for field_data in self.targeted_fields_per_note[card.nid]:

                for index, word_token in enumerate(field_data.field_value_tokenized):

                    if word_token not in words_presence:
                        words_presence[word_token] = []

                    word_presence_score = TextProcessing.calc_word_presence_score(word_token, field_data.field_value_tokenized, index)
                    words_presence[word_token].append(word_presence_score)

        return words_presence

    @cached_property
    def cards_per_word(self) -> dict[WordToken, list[TargetCard]]:

        cards_per_word: dict[WordToken, list[TargetCard]] = {}

        for card in self.target_cards.all_cards:

            for field_data in self.targeted_fields_per_note[card.nid]:

                for word_token in field_data.field_value_tokenized:

                    if word_token not in cards_per_word:
                        cards_per_word[word_token] = []

                    cards_per_word[word_token].append(card)

        return cards_per_word

    @cached_property
    def reviewed_words_cards_familiarity_factor(self) -> dict[WordToken, list[float]]:

        reviewed_words_cards_familiarity_factor: dict[WordToken, list[float]] = {}

        for card in self.target_cards.reviewed_cards:

            for field_data in self.targeted_fields_per_note[card.nid]:

                for word_token in field_data.field_value_tokenized:

                    if word_token not in reviewed_words_cards_familiarity_factor:
                        reviewed_words_cards_familiarity_factor[word_token] = []

                    reviewed_words_cards_familiarity_factor[word_token].append(self.cards_familiarity_factor[card.id])

        return reviewed_words_cards_familiarity_factor

    @cached_property
    def reviewed_words(self) -> dict[WordToken, list[TargetCard]]:

        reviewed_words: dict[WordToken, list[TargetCard]] = {}

        for card in self.target_cards.reviewed_cards:

            for field_data in self.targeted_fields_per_note[card.nid]:

                for word_token in field_data.field_value_tokenized:
                    if word_token not in reviewed_words:
                        reviewed_words[word_token] = []
                    reviewed_words[word_token].append(card)

        return reviewed_words

    @cached_property
    def all_words(self) -> set[WordToken]:

        all_words: set[WordToken] = set()

        for note_id in self.targeted_fields_per_note.keys():

            for field_data in self.targeted_fields_per_note[note_id]:

                for word_token in field_data.field_value_tokenized:
                    all_words.add(word_token)

        return all_words

    @cached_property
    def new_words(self) -> set[WordToken]:

        return set(word for word in self.all_words if word not in self.reviewed_words)

    @cached_property
    def word_frequency(self) -> dict[WordToken, float]:

        word_frequency_list = self.language_data.get_word_frequency_list(self.lang_data_id)

        new_word_frequency: dict[WordToken, float] = {}

        for word_token in self.all_words:
            word_frequency = word_frequency_list.get(word_token, 0)
            if word_frequency > 0:
                new_word_frequency[word_token] = word_frequency

        new_word_frequency = sort_dict_floats_values(new_word_frequency)
        new_word_frequency = normalize_dict_positional_floats_values(new_word_frequency)
        return new_word_frequency

    @cached_property
    def ignored_words(self) -> set[str]:

        return self.language_data.get_ignored_words(self.lang_data_id)


class TargetCorpusData:
    """
    Class representing corpus data from target cards.
    """

    targeted_fields_per_note: dict[NoteId, list[NoteFieldContentData]] = field(default_factory=lambda: defaultdict(list))
    content_metrics: dict[CorpusSegmentId, SegmentContentMetrics]
    focus_words_max_familiarity: float
    familiarity_sweetspot_point: Union[float, str]
    suspended_card_value: float
    suspended_leech_card_value: float
    segmentation_strategy: CorpusSegmentationStrategy

    target_cards: TargetCards
    target_fields_per_note_type: dict[str, dict[str, LangDataId]]
    language_data: LanguageData
    cacher: PersistentCacher

    def __init__(self, target_cards: TargetCards, target_fields_per_note_type: dict[str, dict[str, LangDataId]], language_data: LanguageData, cacher: PersistentCacher):

        self.targeted_fields_per_note = {}
        self.content_metrics = {}
        self.focus_words_max_familiarity = 0.28
        self.familiarity_sweetspot_point = "~0.5"
        self.suspended_card_value = 0.25
        self.suspended_leech_card_value = 0.0
        self.segmentation_strategy = CorpusSegmentationStrategy.BY_LANG_DATA_ID

        self.target_cards = target_cards
        self.language_data = language_data
        self.cacher = cacher
        self.target_fields_per_note_type = target_fields_per_note_type

    def create_data(self) -> None:
        """
        Create corpus data for the given target and its cards.
        """

        if len(self.target_cards) == 0:
            return

        if len(self.content_metrics) > 0:
            raise Exception("Data already created by TargetCorpusData.")

        self.__set_targeted_fields_data()

    def __set_targeted_fields_data(self):

        self.cacher.pre_load_all_items()

        cards_familiarity_factor = self.__get_cards_familiarity_factor(self.target_cards.reviewed_cards, self.suspended_card_value, self.suspended_leech_card_value)

        for note in self.target_cards.get_notes_from_all_cards().values():

            note_type = self.target_cards.get_model(note.mid)

            if (note_type is None):
                raise Exception("Card note type not found for card.nid '{}'!".format(note.mid))
            if note_type['name'] not in self.target_fields_per_note_type:  # note type name is not defined as target
                continue

            target_note_fields = self.target_fields_per_note_type[note_type['name']]

            card_note_fields_in_target: list[NoteFieldContentData] = []

            for field_name, field_val in note.items():
                if field_name in target_note_fields.keys():

                    lang_data_id = target_note_fields[field_name]
                    lang_id = LanguageData.get_lang_id_from_data_id(lang_data_id)

                    if self.segmentation_strategy == CorpusSegmentationStrategy.BY_LANG_DATA_ID:
                        corpus_segment_id = str(lang_data_id)
                    elif self.segmentation_strategy == CorpusSegmentationStrategy.BY_LANG_ID:
                        corpus_segment_id = str(lang_id)
                    elif self.segmentation_strategy == CorpusSegmentationStrategy.BY_NOTE_MODEL_ID_AND_FIELD_NAME:
                        corpus_segment_id = str(note_type['id'])+" => "+field_name
                    else:
                        raise Exception("Invalid segmentation_strategy set!")

                    corpus_segment_id = CorpusSegmentId(corpus_segment_id)

                    content_data = NoteFieldContentData(
                        corpus_segment_id=corpus_segment_id,
                        field_name=field_name,
                        field_value=field_val,
                        target_language_data_id=lang_data_id,
                        target_language_id=lang_id,
                        cacher=self.cacher
                    )

                    card_note_fields_in_target.append(content_data)

                    if corpus_segment_id not in self.content_metrics:
                        segment_content_metrics = SegmentContentMetrics(
                            lang_id,
                            lang_data_id,
                            self.focus_words_max_familiarity,
                            self.familiarity_sweetspot_point,
                            self.target_cards,
                            self.language_data,
                            cards_familiarity_factor
                        )
                        self.content_metrics[corpus_segment_id] = segment_content_metrics
                    elif self.content_metrics[corpus_segment_id].lang_id != lang_id:
                        raise Exception("Language id mismatch for segment '{}' and lang_id '{}'!".format(corpus_segment_id, lang_id))
                    elif self.content_metrics[corpus_segment_id].lang_data_id != lang_data_id:
                        raise Exception("Language data id mismatch for segment '{}' and lang_data_id '{}'!".format(corpus_segment_id, lang_data_id))

                    self.content_metrics[corpus_segment_id].targeted_fields_per_note[note.id].append(content_data)

            self.targeted_fields_per_note[note.id] = card_note_fields_in_target

    @cached_property
    def segments_ids(self) -> Sequence[CorpusSegmentId]:
        return list(self.content_metrics.keys())

    @staticmethod
    def __get_cards_familiarity_score(cards: Sequence[TargetCard]) -> dict[CardId, float]:

        if not cards:
            return {}

        # get scores

        cards_familiarity: dict[CardId, float] = {}

        def normalize_against_baseline(value: float, baseline: int) -> float:

            normalized = value / baseline
            if normalized > 1:
                normalized = 1+(normalized/10)

            # Soft cap (as normalized grows beyond 1.5, we heavily dampen additional growth):
            if normalized > 1.5:
                excess = normalized - 1.5
                normalized = 1.5 + (excess / (1 + excess))

            return normalized

        for card in cards:
            if card.reps < 1 or card.ivl < 1:
                card_score = 0
            else:
                card_interval_score = normalize_against_baseline(card.ivl, 300)
                card_ease_score = normalize_against_baseline(card.ease_factor, 2500)
                card_reps_score = normalize_against_baseline(card.reps, 12)
                if card_reps_score > 1:
                    card_reps_score = (0.75+card_reps_score)/1.75
                if card_ease_score > 1:
                    interval_offset = ((card_ease_score+0.7)/1.7)
                elif card_ease_score < 1:
                    interval_offset = ((card_ease_score+0.75)/1.75)
                else:
                    interval_offset = 1
                card_score = ( (card_interval_score*interval_offset) + (card_ease_score/4) + (card_reps_score/100) ) / 1.26

                if card.days_overdue is not None and card.days_overdue > 0:
                    relative_overdue = card.days_overdue/card.ivl
                    dev = (1+relative_overdue)**3
                    card_score = card_score/dev
            assert card_score < 2
            cards_familiarity[card.id] = card_score

        # done
        return cards_familiarity

    @staticmethod
    def __get_cards_familiarity_factor(cards: Sequence[TargetCard], suspended_card_value: float, suspended_leech_card_value: float) -> dict[CardId, float]:

        cards_familiarity_value = TargetCorpusData.__get_cards_familiarity_score(cards)

        for card in cards:
            if card.is_suspended:
                if card.is_leech:
                    cards_familiarity_value[card.id] = cards_familiarity_value[card.id]*suspended_leech_card_value
                else:
                    cards_familiarity_value[card.id] = cards_familiarity_value[card.id]*suspended_card_value

        # devalue cards from same note (devalue exponentially more as more cards from same note are found)

        cards_familiarity_value = sort_dict_floats_values(cards_familiarity_value)

        note_count: dict[NoteId, int] = {}
        cards_note_ids: dict[CardId, NoteId] = {card.id: card.nid for card in cards}

        for card_id in cards_familiarity_value.keys():

            note_id = cards_note_ids[card_id]

            if note_id not in note_count:
                note_count[note_id] = 1
            else:
                note_count[note_id] += 1
                devalue_factor = 2**(note_count[note_id]-1)
                cards_familiarity_value[card_id] = cards_familiarity_value[card_id]/devalue_factor

        return cards_familiarity_value
