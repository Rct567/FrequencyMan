from dataclasses import dataclass, field
from math import fsum
from statistics import fmean, mean, median
from typing import Iterable, NewType, Type, TypedDict, Union

from anki.collection import Collection
from anki.cards import CardId, Card
from anki.notes import NoteId

from .word_frequency_list import LangId, LangKey, WordFrequencyLists
from .lib.utilities import *
from .target import Target
from .text_processing import TextProcessing, WordToken

# unique id for a field of a note model (basically, just note type id + field name)
# We use this because the corpus data is per field.
FieldKey = NewType('FieldKey', str)

# Meta data for each field (in target)


@dataclass(frozen=True)
class TargetFieldData:
    field_key: FieldKey
    field_name: str
    field_value_plain_text: str
    field_value_tokenized: list[WordToken]
    target_language_key: LangKey
    target_language_id: LangId


# Data of content in fields (in target)
@dataclass
class NoteFieldContentData:
    # reviewed words and the cards they they occur in, per "field of note"
    reviewed_words: dict[FieldKey, dict[WordToken, list[Card]]] = field(default_factory=dict)
    # a list of 'occurrence ratings' per word in a card, per "field of note"
    reviewed_words_occurrences: dict[FieldKey, dict[WordToken, list[float]]] = field(default_factory=dict)  # list because a word can occur multiple times in a field
    # how much a word is 'present' in reviewed cards, per "field of note"
    reviewed_words_familiarity: dict[FieldKey, dict[WordToken, float]] = field(default_factory=dict)
    reviewed_words_familiarity_mean: dict[FieldKey, float] = field(default_factory=dict)
    reviewed_words_familiarity_median: dict[FieldKey, float] = field(default_factory=dict)
    reviewed_words_familiarity_positional: dict[FieldKey, dict[WordToken, float]] = field(default_factory=dict)
    #
    reviewed_words_low_familiarity: dict[FieldKey, dict[WordToken, float]] = field(default_factory=dict)
    #
    words_lexical_discrepancy: dict[FieldKey, dict[WordToken, float]] = field(default_factory=dict)


class TargetCorpusData:
    """
    Class representing corpus data from target cards.
    """

    target_cards: Iterable[Card]
    fields_per_card_note: dict[NoteId, list[TargetFieldData]]
    notes_fields_data: NoteFieldContentData

    def __init__(self):

        self.fields_per_card_note = {}
        self.notes_fields_data = NoteFieldContentData()

    def create_data(self, target_cards: Iterable[Card], target: Target, col: Collection, word_frequency_lists: WordFrequencyLists) -> None:
        """
        Create corpus data for the given target and its cards.
        """

        self.target_cards = target_cards
        target_fields_by_notes_name = target.get_notes()

        for card in target_cards:

            if card.nid not in self.fields_per_card_note:

                card_note = col.get_note(card.nid)
                card_note_type = col.models.get(card_note.mid)

                if (card_note_type is None):
                    raise Exception(f"Card note type not found for card.nid={card_note.mid}!")
                if card_note_type['name'] not in target_fields_by_notes_name:  # note type name is not defined as target
                    continue

                target_note_fields = target_fields_by_notes_name[card_note_type['name']]

                card_note_fields_in_target: list[TargetFieldData] = []
                for field_name, field_val in card_note.items():
                    if field_name in target_note_fields.keys():

                        field_key = str(card_note_type['id'])+" => "+field_name

                        lang_key = target_note_fields[field_name].lower()
                        lang_id = lang_key
                        if (len(lang_id) > 3 and lang_id[2] == '_'):
                            lang_id = lang_id[:2]

                        plain_text = TextProcessing.get_plain_text(field_val).lower()
                        field_value_tokenized = TextProcessing.get_word_tokens_from_text(plain_text, lang_id)

                        card_note_fields_in_target.append(TargetFieldData(
                            field_key=FieldKey(field_key),
                            field_name=field_name,
                            field_value_plain_text=plain_text,
                            field_value_tokenized=field_value_tokenized,
                            target_language_key=LangKey(lang_key),
                            target_language_id=LangId(lang_id)
                        ))

                self.fields_per_card_note[card.nid] = card_note_fields_in_target

        self.__set_notes_reviewed_words()
        self.__set_notes_reviewed_words_familiarity()
        self.__set_notes_reviewed_words_low_familiarity()
        self.__set_notes_lexical_discrepancy(word_frequency_lists)

    def __set_notes_reviewed_words(self) -> None:

        for card in self.target_cards:

            # set reviewed words, and reviewed words occurrences, per field of note

            card_has_been_reviewed = card.type == 2 and card.queue != 0  # card is of type 'review' and queue is not 'new'
            if not card_has_been_reviewed:
                continue

            for field_data in self.fields_per_card_note[card.nid]:

                field_value_num_tokens = len(field_data.field_value_tokenized)
                field_key = field_data.field_key

                for word_token in field_data.field_value_tokenized:
                    # set reviewed words (word has been in a reviewed card)
                    if field_key not in self.notes_fields_data.reviewed_words:
                        self.notes_fields_data.reviewed_words[field_key] = {}
                    if word_token not in self.notes_fields_data.reviewed_words[field_key]:
                        self.notes_fields_data.reviewed_words[field_key][word_token] = []
                    self.notes_fields_data.reviewed_words[field_key][word_token].append(card)
                    # set presence_score for reviewed words
                    if field_key not in self.notes_fields_data.reviewed_words_occurrences:
                        self.notes_fields_data.reviewed_words_occurrences[field_key] = {}
                    if word_token not in self.notes_fields_data.reviewed_words_occurrences[field_key]:
                        self.notes_fields_data.reviewed_words_occurrences[field_key][word_token] = []
                    token_presence_score = 1/fmean([field_value_num_tokens, 3])
                    self.notes_fields_data.reviewed_words_occurrences[field_key][word_token].append(token_presence_score)

    def __set_notes_reviewed_words_familiarity(self) -> None:
        """
        Set the familiarity score for each word per field of card note, based on word presence in reviewed cards.
        """
        for field_key in self.notes_fields_data.reviewed_words_occurrences:

            field_all_word_presence_scores = [fsum(word_scores) for word_scores in self.notes_fields_data.reviewed_words_occurrences[field_key].values()]
            field_avg_word_presence_score = fmean(field_all_word_presence_scores)
            field_median_word_presence_score = median(field_all_word_presence_scores)

            if field_key not in self.notes_fields_data.reviewed_words_familiarity:
                self.notes_fields_data.reviewed_words_familiarity[field_key] = {}

            for word_token in self.notes_fields_data.reviewed_words_occurrences[field_key]:

                word_presence_scores = self.notes_fields_data.reviewed_words_occurrences[field_key][word_token]
                word_familiarity_score = fsum(word_presence_scores)  # todo: also incorporate cards review time?

                if (word_familiarity_score > field_avg_word_presence_score*16):
                    word_familiarity_score = fmean([word_familiarity_score] + [field_avg_word_presence_score]*4)
                if (word_familiarity_score > field_avg_word_presence_score*8):
                    word_familiarity_score = fmean([word_familiarity_score] + [field_avg_word_presence_score]*2)
                if (word_familiarity_score > field_avg_word_presence_score):
                    word_familiarity_score = fmean([word_familiarity_score, field_avg_word_presence_score])

                self.notes_fields_data.reviewed_words_familiarity[field_key][word_token] = word_familiarity_score

            # make scores values relative

            self.notes_fields_data.reviewed_words_familiarity[field_key] = normalize_dict_floats_values(self.notes_fields_data.reviewed_words_familiarity[field_key])
            self.notes_fields_data.reviewed_words_familiarity[field_key] = sort_dict_floats_values(self.notes_fields_data.reviewed_words_familiarity[field_key])
            self.notes_fields_data.reviewed_words_familiarity_mean[field_key] = mean(self.notes_fields_data.reviewed_words_familiarity[field_key].values())
            self.notes_fields_data.reviewed_words_familiarity_median[field_key] = median(self.notes_fields_data.reviewed_words_familiarity[field_key].values())

            # also relative, but based on (sorted) position, just like value received from WordFrequencyList.get_word_frequency

            self.notes_fields_data.reviewed_words_familiarity_positional[field_key] = {}
            max_rank = len(self.notes_fields_data.reviewed_words_familiarity[field_key])

            for index, (word_token, familiarity) in enumerate(self.notes_fields_data.reviewed_words_familiarity[field_key].items()):
                familiarity_positional = (max_rank-(index))/max_rank
                self.notes_fields_data.reviewed_words_familiarity_positional[field_key][word_token] = familiarity_positional

    def __set_notes_reviewed_words_low_familiarity(self) -> None:

        for field_key in self.notes_fields_data.reviewed_words_familiarity:

            if field_key not in self.notes_fields_data.reviewed_words_low_familiarity:
                self.notes_fields_data.reviewed_words_low_familiarity[field_key] = {}

            median_familiarity = median(self.notes_fields_data.reviewed_words_familiarity[field_key].values())

            for word_token in self.notes_fields_data.reviewed_words_familiarity[field_key]:

                familiarity = self.notes_fields_data.reviewed_words_familiarity[field_key][word_token]

                if (familiarity > median_familiarity*2):
                    continue

                low_familiarity_rating = 1-familiarity

                self.notes_fields_data.reviewed_words_low_familiarity[field_key][word_token] = low_familiarity_rating

            self.notes_fields_data.reviewed_words_low_familiarity[field_key] = normalize_dict_floats_values(self.notes_fields_data.reviewed_words_low_familiarity[field_key])
            self.notes_fields_data.reviewed_words_low_familiarity[field_key] = sort_dict_floats_values(self.notes_fields_data.reviewed_words_low_familiarity[field_key])

    def get_words_lexical_discrepancy(self, field_key: FieldKey, word_token: WordToken) -> float:

        if not self.notes_fields_data.words_lexical_discrepancy:
            raise Exception("Target corpus data not loaded!")

        return self.notes_fields_data.words_lexical_discrepancy[field_key][word_token]  # unfamiliarity of high frequency words

    def __set_notes_lexical_discrepancy(self, word_frequency_lists: WordFrequencyLists) -> None:

        for note_fields in self.fields_per_card_note.values():

            for field in note_fields:

                field_key = field.field_key
                language_key = field.target_language_key

                if (field_key not in self.notes_fields_data.words_lexical_discrepancy):
                    self.notes_fields_data.words_lexical_discrepancy[field_key] = {}

                for word_token in field.field_value_tokenized:

                    word_fr = word_frequency_lists.get_word_frequency(language_key, word_token, 0)
                    word_familiarity = self.notes_fields_data.reviewed_words_familiarity_positional[field_key].get(word_token, 0)
                    word_lexical_discrepancy_rating = (word_fr - word_familiarity)
                    if (word_lexical_discrepancy_rating < 0):
                        word_lexical_discrepancy_rating = 0.0

                    self.notes_fields_data.words_lexical_discrepancy[field_key][word_token] = word_lexical_discrepancy_rating

        for field_key in self.notes_fields_data.words_lexical_discrepancy.keys():
            self.notes_fields_data.words_lexical_discrepancy[field_key] = normalize_dict_floats_values(self.notes_fields_data.words_lexical_discrepancy[field_key])
            self.notes_fields_data.words_lexical_discrepancy[field_key] = sort_dict_floats_values(self.notes_fields_data.words_lexical_discrepancy[field_key])
