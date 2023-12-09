from collections import defaultdict
from dataclasses import dataclass, field
from math import fsum
from statistics import fmean, mean, median
from typing import Iterable, NewType, Type, TypedDict, Union

from anki.collection import Collection
from anki.cards import CardId, Card
from anki.notes import NoteId

from .word_frequency_list import LangId, LangKey, WordFrequencyLists
from .lib.utilities import *
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
    reviewed_words: dict[FieldKey, dict[WordToken, list[Card]]] = field(default_factory=lambda: defaultdict(dict))
    #
    reviewed_words_presence: dict[FieldKey, dict[WordToken, list[float]]] = field(default_factory=lambda: defaultdict(dict))  # list because a word can occur multiple times in a field
    #
    reviewed_words_familiarity: dict[FieldKey, dict[WordToken, float]] = field(default_factory=lambda: defaultdict(dict))
    reviewed_words_familiarity_mean: dict[FieldKey, float] = field(default_factory=dict)
    reviewed_words_familiarity_median: dict[FieldKey, float] = field(default_factory=dict)
    #
    reviewed_words_familiarity_positional: dict[FieldKey, dict[WordToken, float]] = field(default_factory=lambda: defaultdict(dict))
    #
    reviewed_words_familiarity_sweetspot: dict[FieldKey, dict[WordToken, float]] = field(default_factory=lambda: defaultdict(dict))
    #
    words_lexical_discrepancy: dict[FieldKey, dict[WordToken, float]] = field(default_factory=lambda: defaultdict(dict))


class TargetCorpusData:
    """
    Class representing corpus data from target cards.
    """

    target_cards_reviewed: Iterable[Card]
    fields_per_card_note: dict[NoteId, list[TargetFieldData]]
    notes_fields_data: NoteFieldContentData

    def __init__(self):

        self.fields_per_card_note = {}
        self.notes_fields_data = NoteFieldContentData()

    def create_data(self, target_cards: Iterable[Card], target_fields_by_notes_name: dict[str, dict[str, str]], col: Collection, word_frequency_lists: WordFrequencyLists) -> None:
        """
        Create corpus data for the given target and its cards.
        """

        self.target_cards_reviewed = []

        if not target_cards:
            return

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

            if card.type == 2 and card.queue != 0:  # card is of type 'review' and queue is not 'new'
                self.target_cards_reviewed.append(card)

        self.__set_notes_reviewed_words()
        self.__set_notes_reviewed_words_familiarity()
        self.__set_notes_reviewed_words_familiarity_sweetspot()
        self.__set_notes_lexical_discrepancy(word_frequency_lists)

    def __get_reviewed_words_card_memorized_scores(self) -> dict[CardId, float]:

        cards_interval: list[int] = []
        cards_reps: list[int] = []
        cards_ease: list[int] = []

        for card in self.target_cards_reviewed:
            cards_interval.append(card.ivl)
            cards_reps.append(card.reps)
            cards_ease.append(card.factor)

        # smooth out top values

        for metric_list, turnover_val in [(cards_interval, 30*7), (cards_reps, 14)]:
            for index in range(len(metric_list)):
                if metric_list[index] > turnover_val:
                    metric_list[index] = mean([turnover_val, metric_list[index]])

        # get scores

        card_memorized_scores: dict[CardId, float] = {}

        cards_interval_max = max(cards_interval)
        cards_reps_max = max(cards_reps)
        cards_ease_max = max(cards_ease)

        for card in self.target_cards_reviewed:
            card_memorized_scores[card.id] = fmean([(card.ivl/cards_interval_max), (card.reps/cards_reps_max), (card.factor/cards_ease_max)])

        card_memorized_scores = normalize_dict_floats_values(card_memorized_scores)
        card_memorized_scores = sort_dict_floats_values(card_memorized_scores)

        return card_memorized_scores

    def __set_notes_reviewed_words(self) -> None:

        card_memorized_scores = self.__get_reviewed_words_card_memorized_scores()

        for card in self.target_cards_reviewed:

            for field_data in self.fields_per_card_note[card.nid]:

                field_value_num_tokens = len(field_data.field_value_tokenized)
                field_key = field_data.field_key

                for word_token in field_data.field_value_tokenized:
                    # set reviewed words (word has been in a reviewed card)
                    if word_token not in self.notes_fields_data.reviewed_words[field_key]:
                        self.notes_fields_data.reviewed_words[field_key][word_token] = []
                    self.notes_fields_data.reviewed_words[field_key][word_token].append(card)
                    # set presence score for reviewed words
                    if word_token not in self.notes_fields_data.reviewed_words_presence[field_key]:
                        self.notes_fields_data.reviewed_words_presence[field_key][word_token] = []
                    token_presence_score = ( (1+(1/field_value_num_tokens)) ** 1.5 ) * (1+card_memorized_scores[card.id])
                    self.notes_fields_data.reviewed_words_presence[field_key][word_token].append(token_presence_score)

    def __set_notes_reviewed_words_familiarity(self) -> None:
        """
        Set the familiarity score for each word per field of card note, based on word presence in reviewed cards.
        """
        for field_key in self.notes_fields_data.reviewed_words_presence:

            field_all_word_presence_scores = [fsum(word_scores) for word_scores in self.notes_fields_data.reviewed_words_presence[field_key].values()]
            field_avg_word_presence_score = fmean(field_all_word_presence_scores)

            for word_token in self.notes_fields_data.reviewed_words_presence[field_key]:

                word_presence_scores = self.notes_fields_data.reviewed_words_presence[field_key][word_token]
                word_presence_score = fsum(word_presence_scores)

                if (word_presence_score > field_avg_word_presence_score*16):
                    word_presence_score = fmean([word_presence_score] + [field_avg_word_presence_score]*4)
                if (word_presence_score > field_avg_word_presence_score*8):
                    word_presence_score = fmean([word_presence_score] + [field_avg_word_presence_score]*2)
                if (word_presence_score > field_avg_word_presence_score):
                    word_presence_score = fmean([word_presence_score, field_avg_word_presence_score])

                word_familiarity_score = word_presence_score

                self.notes_fields_data.reviewed_words_familiarity[field_key][word_token] = word_familiarity_score

            # make scores values relative

            self.notes_fields_data.reviewed_words_familiarity[field_key] = normalize_dict_floats_values(self.notes_fields_data.reviewed_words_familiarity[field_key])
            self.notes_fields_data.reviewed_words_familiarity[field_key] = sort_dict_floats_values(self.notes_fields_data.reviewed_words_familiarity[field_key])

            # set avg

            self.notes_fields_data.reviewed_words_familiarity_mean[field_key] = mean(self.notes_fields_data.reviewed_words_familiarity[field_key].values())
            self.notes_fields_data.reviewed_words_familiarity_median[field_key] = median(self.notes_fields_data.reviewed_words_familiarity[field_key].values())

            # also relative, but based on (sorted) position, just like value received from WordFrequencyList.get_word_frequency

            max_rank = len(self.notes_fields_data.reviewed_words_familiarity[field_key])

            for index, (word_token, familiarity) in enumerate(self.notes_fields_data.reviewed_words_familiarity[field_key].items()):
                familiarity_positional = (max_rank-(index))/max_rank
                self.notes_fields_data.reviewed_words_familiarity_positional[field_key][word_token] = familiarity_positional

    def __set_notes_reviewed_words_familiarity_sweetspot(self) -> None:

        for field_key in self.notes_fields_data.reviewed_words_familiarity:

            median_familiarity = median(self.notes_fields_data.reviewed_words_familiarity[field_key].values())

            for word_token in self.notes_fields_data.reviewed_words_familiarity[field_key]:

                familiarity = self.notes_fields_data.reviewed_words_familiarity[field_key][word_token]

                if (familiarity > median_familiarity*2):
                    continue

                familiarity_sweetspot_rating = 1-abs(familiarity-(median_familiarity*0.75))

                self.notes_fields_data.reviewed_words_familiarity_sweetspot[field_key][word_token] = familiarity_sweetspot_rating

            self.notes_fields_data.reviewed_words_familiarity_sweetspot[field_key] = normalize_dict_floats_values(self.notes_fields_data.reviewed_words_familiarity_sweetspot[field_key])
            self.notes_fields_data.reviewed_words_familiarity_sweetspot[field_key] = sort_dict_floats_values(self.notes_fields_data.reviewed_words_familiarity_sweetspot[field_key])

    def get_words_lexical_discrepancy(self, field_key: FieldKey, word_token: WordToken) -> float:

        if not self.notes_fields_data.words_lexical_discrepancy:
            raise Exception("Target corpus data not loaded!")

        try:
            return self.notes_fields_data.words_lexical_discrepancy[field_key][word_token]  # unfamiliarity of high frequency words
        except KeyError:
            return 0.0

    def __set_notes_lexical_discrepancy(self, word_frequency_lists: WordFrequencyLists) -> None:

        for note_fields in self.fields_per_card_note.values():

            for field in note_fields:

                field_key = field.field_key
                language_key = field.target_language_key

                for word_token in field.field_value_tokenized:

                    word_fr = word_frequency_lists.get_word_frequency(language_key, word_token, 0)
                    word_familiarity = self.notes_fields_data.reviewed_words_familiarity_positional[field_key].get(word_token, 0)
                    word_lexical_discrepancy_rating = (word_fr - word_familiarity)
                    if (word_lexical_discrepancy_rating >= 0):
                        self.notes_fields_data.words_lexical_discrepancy[field_key][word_token] = word_lexical_discrepancy_rating

        for field_key in self.notes_fields_data.words_lexical_discrepancy.keys():
            self.notes_fields_data.words_lexical_discrepancy[field_key] = normalize_dict_floats_values(self.notes_fields_data.words_lexical_discrepancy[field_key])
            self.notes_fields_data.words_lexical_discrepancy[field_key] = sort_dict_floats_values(self.notes_fields_data.words_lexical_discrepancy[field_key])
