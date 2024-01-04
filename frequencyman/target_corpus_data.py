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

from .target_cards import TargetCards
from .word_frequency_list import LangId, LangKey, WordFrequencyLists
from .lib.utilities import *
from .text_processing import TextProcessing, WordToken


# This is used to make the corpus data per field.
# It is created by using model.id and note field name.
# It could be changed to make it per LangId (thus merging multiple note field
# when they have to same LangId)
CorpusId = NewType('CorpusId', str)

# Meta data for each field (in target)
@dataclass(frozen=True)
class TargetFieldData:
    corpus_id: CorpusId
    field_name: str
    field_value_plain_text: str
    field_value_tokenized: list[WordToken]
    target_language_key: LangKey
    target_language_id: LangId


# Data of content in fields (in target)
@dataclass
class NoteFieldContentData:
    # reviewed words and the cards they they occur in, per "field of note"
    reviewed_words: dict[CorpusId, dict[WordToken, list[Card]]] = field(default_factory=lambda: defaultdict(dict))
    #
    reviewed_words_presence: dict[CorpusId, dict[WordToken, list[float]]] = field(default_factory=lambda: defaultdict(dict))  # list because a word can occur multiple times in a field
    reviewed_words_presence_card_score: dict[CorpusId, dict[WordToken, list[float]]] = field(default_factory=lambda: defaultdict(dict))
    #
    reviewed_words_familiarity: dict[CorpusId, dict[WordToken, float]] = field(default_factory=lambda: defaultdict(dict))
    reviewed_words_familiarity_mean: dict[CorpusId, float] = field(default_factory=dict)
    reviewed_words_familiarity_median: dict[CorpusId, float] = field(default_factory=dict)
    #
    reviewed_words_familiarity_positional: dict[CorpusId, dict[WordToken, float]] = field(default_factory=lambda: defaultdict(dict))
    #
    reviewed_words_familiarity_sweetspot: dict[CorpusId, dict[WordToken, float]] = field(default_factory=lambda: defaultdict(dict))
    #
    words_lexical_discrepancy: dict[CorpusId, dict[WordToken, float]] = field(default_factory=lambda: defaultdict(dict))


class TargetCorpusData:
    """
    Class representing corpus data from target cards.
    """

    target_cards: TargetCards
    field_data_per_card_note: dict[NoteId, list[TargetFieldData]]
    notes_fields_data: NoteFieldContentData
    familiarity_sweetspot_point: float

    def __init__(self):

        self.field_data_per_card_note = {}
        self.notes_fields_data = NoteFieldContentData()
        self.familiarity_sweetspot_point = 0.75

    def create_data(self, target_cards: TargetCards, target_fields_by_notes_name: dict[str, dict[str, str]], word_frequency_lists: WordFrequencyLists) -> None:
        """
        Create corpus data for the given target and its cards.
        """

        if len(target_cards) == 0:
            return

        self.target_cards = target_cards

        for card in target_cards.get_all_cards():

            if card.nid not in self.field_data_per_card_note:

                card_note = target_cards.get_note(card.nid)
                card_note_type = target_cards.get_model(card_note.mid)

                if (card_note_type is None):
                    raise Exception("Card note type not found for card.nid '{}'!".format(card_note.mid))
                if card_note_type['name'] not in target_fields_by_notes_name:  # note type name is not defined as target
                    continue

                target_note_fields = target_fields_by_notes_name[card_note_type['name']]

                card_note_fields_in_target: list[TargetFieldData] = []
                for field_name, field_val in card_note.items():
                    if field_name in target_note_fields.keys():

                        corpus_id = str(card_note_type['id'])+" => "+field_name

                        lang_key = target_note_fields[field_name].lower()
                        lang_id = lang_key
                        if (len(lang_id) > 3 and lang_id[2] == '_'):
                            lang_id = lang_id[:2]

                        plain_text = TextProcessing.get_plain_text(field_val).lower()
                        field_value_tokenized = TextProcessing.get_word_tokens_from_text(plain_text, lang_id)

                        card_note_fields_in_target.append(TargetFieldData(
                            corpus_id=CorpusId(corpus_id),
                            field_name=field_name,
                            field_value_plain_text=plain_text,
                            field_value_tokenized=field_value_tokenized,
                            target_language_key=LangKey(lang_key),
                            target_language_id=LangId(lang_id)
                        ))

                self.field_data_per_card_note[card.nid] = card_note_fields_in_target

        self.__set_notes_reviewed_words()
        self.__set_notes_reviewed_words_presence()
        self.__set_notes_reviewed_words_familiarity()
        self.__set_notes_reviewed_words_familiarity_sweetspot()
        self.__set_notes_lexical_discrepancy(word_frequency_lists)

    def __get_reviewed_words_card_memorized_scores(self) -> dict[CardId, float]:

        cards_interval: list[float] = []
        cards_reps: list[float] = []
        cards_ease: list[float] = []

        for card in self.target_cards.get_reviewed_cards():
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

        for card in self.target_cards.get_reviewed_cards():
            card_memorized_scores[card.id] = fmean([(card.ivl/cards_interval_max), (card.reps/cards_reps_max), (card.factor/cards_ease_max)])

        card_memorized_scores = normalize_dict_floats_values(card_memorized_scores)
        card_memorized_scores = sort_dict_floats_values(card_memorized_scores)

        return card_memorized_scores

    def __set_notes_reviewed_words(self) -> None:

        for card in self.target_cards.get_reviewed_cards():

            for field_data in self.field_data_per_card_note[card.nid]:

                corpus_key = field_data.corpus_id

                for word_token in field_data.field_value_tokenized:
                    if word_token not in self.notes_fields_data.reviewed_words[corpus_key]:
                        self.notes_fields_data.reviewed_words[corpus_key][word_token] = []
                    self.notes_fields_data.reviewed_words[corpus_key][word_token].append(card)

    @staticmethod
    def __calc_word_presence_score(word_token: str, context_num_chars :int, context_num_tokens: int, position_index: int) -> float:

        presence_num_chars = len(word_token)/context_num_chars
        presence_num_tokens = 1/context_num_tokens
        position_value = 1/(position_index+1)
        return (presence_num_chars+presence_num_tokens+position_value)/3

    def __set_notes_reviewed_words_presence(self) -> None:

        card_memorized_scores = self.__get_reviewed_words_card_memorized_scores()

        for card in self.target_cards.get_reviewed_cards():

            for field_data in self.field_data_per_card_note[card.nid]:

                corpus_key = field_data.corpus_id
                field_num_tokens = len(field_data.field_value_tokenized)
                field_num_chars_tokens = len(''.join(field_data.field_value_tokenized))

                for index, word_token in enumerate(field_data.field_value_tokenized):

                    if word_token not in self.notes_fields_data.reviewed_words_presence[corpus_key]:
                        self.notes_fields_data.reviewed_words_presence[corpus_key][word_token] = []
                        self.notes_fields_data.reviewed_words_presence_card_score[corpus_key][word_token] = []

                    word_presence_score = self.__calc_word_presence_score(word_token, field_num_chars_tokens, field_num_tokens, index)
                    self.notes_fields_data.reviewed_words_presence[corpus_key][word_token].append(word_presence_score)
                    self.notes_fields_data.reviewed_words_presence_card_score[corpus_key][word_token].append(card_memorized_scores[card.id])

    def __set_notes_reviewed_words_familiarity(self) -> None:
        """
        Set the familiarity score for each word per field of card note, based on word presence in reviewed cards and score of card.
        """
        for corpus_key in self.notes_fields_data.reviewed_words_presence:

            field_familiarity_scores_per_word: list[float] = []

            for word_token, word_presence_scores in self.notes_fields_data.reviewed_words_presence[corpus_key].items():
                word_presence_card_scores = self.notes_fields_data.reviewed_words_presence_card_score[corpus_key][word_token]
                field_familiarity_scores_per_word.append(fsum(word_presence_scores)+fsum(word_presence_card_scores))

            field_avg_word_familiarity_score = fmean(field_familiarity_scores_per_word)

            for index, word_token in enumerate(self.notes_fields_data.reviewed_words_presence[corpus_key].keys()):

                word_familiarity_smooth_score = field_familiarity_scores_per_word[index]

                if (word_familiarity_smooth_score > field_avg_word_familiarity_score*16):
                    word_familiarity_smooth_score = fmean([word_familiarity_smooth_score] + [field_avg_word_familiarity_score]*4)
                if (word_familiarity_smooth_score > field_avg_word_familiarity_score*8):
                    word_familiarity_smooth_score = fmean([word_familiarity_smooth_score] + [field_avg_word_familiarity_score]*2)
                if (word_familiarity_smooth_score > field_avg_word_familiarity_score):
                    word_familiarity_smooth_score = fmean([word_familiarity_smooth_score, field_avg_word_familiarity_score])

                self.notes_fields_data.reviewed_words_familiarity[corpus_key][word_token] = word_familiarity_smooth_score

            # make scores values relative

            self.notes_fields_data.reviewed_words_familiarity[corpus_key] = normalize_dict_floats_values(self.notes_fields_data.reviewed_words_familiarity[corpus_key])
            self.notes_fields_data.reviewed_words_familiarity[corpus_key] = sort_dict_floats_values(self.notes_fields_data.reviewed_words_familiarity[corpus_key])

            # set avg and median

            self.notes_fields_data.reviewed_words_familiarity_mean[corpus_key] = mean(self.notes_fields_data.reviewed_words_familiarity[corpus_key].values())
            self.notes_fields_data.reviewed_words_familiarity_median[corpus_key] = median(self.notes_fields_data.reviewed_words_familiarity[corpus_key].values())

            # also relative, but based on (sorted) position, just like value received from WordFrequencyList.get_word_frequency

            max_rank = len(self.notes_fields_data.reviewed_words_familiarity[corpus_key])

            for index, word_token in enumerate(self.notes_fields_data.reviewed_words_familiarity[corpus_key].keys()):
                familiarity_positional = (max_rank-(index))/max_rank
                self.notes_fields_data.reviewed_words_familiarity_positional[corpus_key][word_token] = familiarity_positional

    def __set_notes_reviewed_words_familiarity_sweetspot(self) -> None:

        for corpus_key in self.notes_fields_data.reviewed_words_familiarity:

            median_familiarity = median(self.notes_fields_data.reviewed_words_familiarity[corpus_key].values())

            for word_token in self.notes_fields_data.reviewed_words_familiarity[corpus_key]:

                familiarity = self.notes_fields_data.reviewed_words_familiarity[corpus_key][word_token]
                familiarity_sweetspot_value = median_familiarity*self.familiarity_sweetspot_point

                if (familiarity > familiarity_sweetspot_value*2.6666):
                    continue

                familiarity_sweetspot_rating = 1-abs(familiarity-familiarity_sweetspot_value)

                self.notes_fields_data.reviewed_words_familiarity_sweetspot[corpus_key][word_token] = familiarity_sweetspot_rating

            self.notes_fields_data.reviewed_words_familiarity_sweetspot[corpus_key] = normalize_dict_floats_values(self.notes_fields_data.reviewed_words_familiarity_sweetspot[corpus_key])
            self.notes_fields_data.reviewed_words_familiarity_sweetspot[corpus_key] = sort_dict_floats_values(self.notes_fields_data.reviewed_words_familiarity_sweetspot[corpus_key])

    def get_words_lexical_discrepancy(self, corpus_key: CorpusId, word_token: WordToken) -> float:

        if not self.notes_fields_data.words_lexical_discrepancy:
            raise Exception("Target corpus data not loaded!")

        try:
            return self.notes_fields_data.words_lexical_discrepancy[corpus_key][word_token]  # unfamiliarity of high frequency words
        except KeyError:
            return 0.0

    def __set_notes_lexical_discrepancy(self, word_frequency_lists: WordFrequencyLists) -> None:

        for note_fields in self.field_data_per_card_note.values():

            for field in note_fields:

                corpus_key = field.corpus_id
                language_key = field.target_language_key

                for word_token in field.field_value_tokenized:

                    word_fr = word_frequency_lists.get_word_frequency(language_key, word_token, 0)
                    word_familiarity = self.notes_fields_data.reviewed_words_familiarity_positional[corpus_key].get(word_token, 0)
                    word_lexical_discrepancy_rating = (word_fr - word_familiarity)
                    if (word_lexical_discrepancy_rating >= 0):
                        self.notes_fields_data.words_lexical_discrepancy[corpus_key][word_token] = word_lexical_discrepancy_rating

        for corpus_key in self.notes_fields_data.words_lexical_discrepancy.keys():
            self.notes_fields_data.words_lexical_discrepancy[corpus_key] = normalize_dict_floats_values(self.notes_fields_data.words_lexical_discrepancy[corpus_key])
            self.notes_fields_data.words_lexical_discrepancy[corpus_key] = sort_dict_floats_values(self.notes_fields_data.words_lexical_discrepancy[corpus_key])
