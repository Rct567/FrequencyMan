"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from abc import ABC, abstractmethod
from typing import Optional, Union

from aqt.utils import showInfo, askUser, showWarning

from ..text_processing import WordToken
from ..target_corpus_data import TargetCorpusData, SegmentContentMetrics, CorpusSegmentId

from ..lib.utilities import var_dump_log, override


class AdditionalColumn(ABC):

    title: str

    @abstractmethod
    def get_values(self, words: list[WordToken], metrics: SegmentContentMetrics) -> list[Union[float, int, str]]:
        pass

    def should_hide(self, current_labels: list[str]) -> bool:
        return self.title in current_labels


class WordFrequencyColumn(AdditionalColumn):

    title = "Word frequency"

    @override
    def get_values(self, words: list[WordToken], metrics: SegmentContentMetrics) -> list[Union[float, int, str]]:
        return [metrics.word_frequency.get(word, 0.0) for word in words]


class WordFamiliarityColumn(AdditionalColumn):

    title = "Familiarity"

    @override
    def get_values(self, words: list[WordToken], metrics: SegmentContentMetrics) -> list[Union[float, int, str]]:
        return [metrics.words_familiarity.get(word, 0.0) for word in words]


class NumberOfCardsColumn(AdditionalColumn):

    title = "Number of cards"

    @override
    def get_values(self, words: list[WordToken], metrics: SegmentContentMetrics) -> list[Union[float, int, str]]:
        return [len(set(card.id for card in metrics.cards_per_word.get(word, []))) for word in words]

class NumberOfNotesColumn(AdditionalColumn):

    title = "Number of notes"

    @override
    def get_values(self, words: list[WordToken], metrics: SegmentContentMetrics) -> list[Union[float, int, str]]:
        return [len(set(card.nid for card in metrics.cards_per_word.get(word, []))) for word in words]