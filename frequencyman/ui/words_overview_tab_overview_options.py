"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from abc import ABC, abstractmethod
from typing import Union

from aqt.utils import showWarning

from ..text_processing import WordToken
from ..target_corpus_data import SegmentContentMetrics, CorpusSegmentId
from ..target import Target

from ..lib.utilities import override


TableDataType = list[tuple[WordToken, list[Union[float, int]]]]

class WordsOverviewOption(ABC):

    title: str
    selected_target: Target
    selected_corpus_segment_id: CorpusSegmentId
    selected_corpus_content_metrics: SegmentContentMetrics

    def __init__(self, selected_target: Target, selected_corpus_segment_id: CorpusSegmentId, selected_corpus_content_metrics: SegmentContentMetrics):
        self.selected_target = selected_target
        self.selected_corpus_segment_id = selected_corpus_segment_id
        self.selected_corpus_content_metrics = selected_corpus_content_metrics

    @abstractmethod
    def data_description(self) -> str:
        pass

    @abstractmethod
    def data(self) -> TableDataType:
        pass

    @abstractmethod
    def labels(self) -> list[str]:
        pass


class WordFamiliarityOverview(WordsOverviewOption):

    title = "Word familiarity"

    @override
    def data_description(self) -> str:
        return "Word familiarity for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> TableDataType:
        return [(word, [familiarity]) for word, familiarity in self.selected_corpus_content_metrics.words_familiarity.items()]

    @override
    def labels(self) -> list[str]:
        return ["Word", "Familiarity"]


class WordFrequencyOverview(WordsOverviewOption):

    title = "Word frequency"

    @override
    def data_description(self) -> str:
        return "Word frequency for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> TableDataType:
        return [(word, [frequency]) for word, frequency in self.selected_corpus_content_metrics.word_frequency.items()]

    @override
    def labels(self) -> list[str]:
        return ["Word", "Word frequency"]


class InternalWordFrequencyOverview(WordsOverviewOption):

    title = "Internal word frequency"

    @override
    def data_description(self) -> str:
        return "Internal word frequency for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> TableDataType:
        return [(word, [frequency]) for word, frequency in self.selected_corpus_content_metrics.internal_word_frequency.items()]

    @override
    def labels(self) -> list[str]:
        return ["Word", "Internal word frequency"]


class WordUnderexposureOverview(WordsOverviewOption):

    title = "Word underexposure"

    @override
    def data_description(self) -> str:
        return "Word underexposure for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> TableDataType:
        return [(word, [underexposure]) for word, underexposure in self.selected_corpus_content_metrics.words_underexposure.items()]

    @override
    def labels(self) -> list[str]:
        return ["Word", "Underexposure"]

class WordFamiliaritySweetspotOverview(WordsOverviewOption):

    title = "Word familiarity sweetspot"

    @override
    def data_description(self) -> str:
        return "Word familiarity sweetspot for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> TableDataType:
        return [(word, [sweetspot]) for word, sweetspot in self.selected_corpus_content_metrics.words_familiarity_sweetspot.items()]

    @override
    def labels(self) -> list[str]:
        return ["Word", "Sweetspot score"]

class MatureWordsOverview(WordsOverviewOption):

    title = "Mature words"

    @override
    def data_description(self) -> str:
        return "Mature words for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> TableDataType:
        return [(word, [familiarity]) for word, familiarity in self.selected_corpus_content_metrics.words_familiarity.items() if word in self.selected_corpus_content_metrics.mature_words]

    @override
    def labels(self) -> list[str]:
        return ["Word", "Familiarity"]

class NotInWordFrequencyListsOverview(WordsOverviewOption):

    title = "Not in word frequency lists"

    @override
    def data_description(self) -> str:
        return "Words not in word frequency lists for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> TableDataType:

        no_fr_words = set(word for word in self.selected_corpus_content_metrics.all_words if word not in self.selected_corpus_content_metrics.word_frequency)
        data: TableDataType = [(word, [len(cards)]) for word, cards in self.selected_corpus_content_metrics.cards_per_word.items() if word in no_fr_words]
        data = sorted(data, key=lambda x: x[1][0], reverse=True)
        return data

    @override
    def labels(self) -> list[str]:
        return ["Word", "Number of cards"]

class NotInTargetCardsOverview(WordsOverviewOption):

    title = "Not in target cards"

    @override
    def data_description(self) -> str:
        return "Words not in target cards for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> TableDataType:

        word_frequency_list = self.selected_corpus_content_metrics.language_data.get_word_frequency_list(self.selected_corpus_content_metrics.lang_data_id)

        if self.selected_corpus_content_metrics.language_data.word_frequency_lists.word_frequency_lists is None:
            showWarning("No word frequency lists loaded.")
            return []

        words_in_frequency_lists_with_position = {word: position+1 for position, word in enumerate(word_frequency_list.keys())}

        words_without_cards: TableDataType = [(WordToken(word), [position]) for word, position in words_in_frequency_lists_with_position.items() if word not in self.selected_corpus_content_metrics.all_words]
        words_without_cards = sorted(words_without_cards, key=lambda x: x[1][0], reverse=False)
        return words_without_cards

    @override
    def labels(self) -> list[str]:
        return ["Word", "Word frequency list position"]

class LonelyWordsOverview(WordsOverviewOption):

    title = "Lonely words"

    @override
    def data_description(self) -> str:
        return "Lonely words (words with only one note) for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> TableDataType:

        num_notes = {word: len(set(card.nid for card in cards)) for word, cards in self.selected_corpus_content_metrics.cards_per_word.items()}
        lonely_words = set(word for word, num_notes in num_notes.items() if num_notes == 1)

        data = [(word, [self.selected_corpus_content_metrics.words_familiarity.get(word, 0.0)]) for word in lonely_words]
        data = sorted(data, key=lambda x: x[1][0], reverse=True)
        return data

    @override
    def labels(self) -> list[str]:
        return ["Word", "Familiarity"]


class AllWordsOverview(WordsOverviewOption):

    title = "All words"

    @override
    def data_description(self) -> str:
        return "All words for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> TableDataType:
        data = [(word, [self.selected_corpus_content_metrics.words_familiarity.get(word, 0.0)]) for word in self.selected_corpus_content_metrics.all_words]
        data = sorted(data, key=lambda x: x[1][0], reverse=True)
        return data

    @override
    def labels(self) -> list[str]:
        return ["Word", "Familiarity"]


class NewWordsOverview(WordsOverviewOption):

    title = "New words"

    @override
    def data_description(self) -> str:
        return "New words (words not yet reviewed) for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> TableDataType:

        new_words = self.selected_corpus_content_metrics.new_words
        data = [(word, [self.selected_corpus_content_metrics.word_frequency.get(word, 0.0)]) for word in new_words]
        data = sorted(data, key=lambda x: x[1][0], reverse=True)
        return data

    @override
    def labels(self) -> list[str]:
        return ["Word", "Word frequency"]


class FocusWordsOverview(WordsOverviewOption):

    title = "Focus words"

    @override
    def data_description(self) -> str:
        return "Focus words for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> TableDataType:

        focus_words = {word for word in self.selected_corpus_content_metrics.all_words if word not in self.selected_corpus_content_metrics.mature_words}
        focus_words_frequency = {word: self.selected_corpus_content_metrics.word_frequency.get(word, 0.0) for word in focus_words}
        focus_words_familiarity = {word: self.selected_corpus_content_metrics.words_familiarity.get(word, 0.0) for word in focus_words}

        data = [(word, [focus_words_frequency[word], focus_words_familiarity[word]]) for word in focus_words]
        data = sorted(data, key=lambda x: x[1][0], reverse=True)
        return data

    @override
    def labels(self) -> list[str]:
        return ["Word", "Word frequency", "Familiarity"]


class LearningWordsOverview(WordsOverviewOption):

    title = "Learning words"

    @override
    def data_description(self) -> str:
        return "Learning words for segment '{}' of target '{}':".format(self.selected_corpus_segment_id, self.selected_target.name)

    @override
    def data(self) -> TableDataType:
        return [(word, [familiarity]) for word, familiarity in self.selected_corpus_content_metrics.words_familiarity.items() if word not in self.selected_corpus_content_metrics.mature_words]

    @override
    def labels(self) -> list[str]:
        return ["Word", "Familiarity"]
