"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from abc import ABC, abstractmethod
from typing import Optional, Union

from .words_overview_tab_overview_options import WordsOverviewOption

from ..target_corpus_data import SegmentContentMetrics, TargetCorpusData, CorpusSegmentId

from ..lib.utilities import var_dump_log, override
from ..text_processing import WordToken


class FilterOption(ABC):

    title: str

    @abstractmethod
    def filter_data(self, data: list[tuple[Union[WordToken, float, int], ...]], metrics: SegmentContentMetrics) -> list[tuple[Union[WordToken, float, int], ...]]:
        pass

    @abstractmethod
    def is_enabled(self, data: list[tuple[Union[WordToken, float, int], ...]], metrics: SegmentContentMetrics) -> bool:
        pass

    @abstractmethod
    def is_hidden(self, overview_option: WordsOverviewOption) -> bool:
        pass


class MatureWordsFilter(FilterOption):

    title = "Mature words"

    @override
    def filter_data(self, data: list[tuple[Union[WordToken, float, int], ...]], metrics: SegmentContentMetrics) -> list[tuple[Union[WordToken, float, int], ...]]:
        return [row for row in data if isinstance(row[0], str) and row[0] in metrics.mature_words]

    @override
    def is_enabled(self, data: list[tuple[Union[WordToken, float, int], ...]], metrics: SegmentContentMetrics) -> bool:
        return any(row for row in data if isinstance(row[0], str) and row[0] in metrics.mature_words)

    @override
    def is_hidden(self, overview_option: WordsOverviewOption) -> bool:
        return overview_option.title in {"Learning words", "Mature words"}


class LearningWordsFilter(FilterOption):

    title = "Learning words"

    @override
    def filter_data(self, data: list[tuple[Union[WordToken, float, int], ...]], metrics: SegmentContentMetrics) -> list[tuple[Union[WordToken, float, int], ...]]:
        return [row for row in data if isinstance(row[0], str) and row[0] in metrics.words_familiarity and row[0] not in metrics.mature_words]

    @override
    def is_enabled(self, data: list[tuple[Union[WordToken, float, int], ...]], metrics: SegmentContentMetrics) -> bool:
        return any(row for row in data if isinstance(row[0], str) and row[0] in metrics.words_familiarity and row[0] not in metrics.mature_words)

    @override
    def is_hidden(self, overview_option: WordsOverviewOption) -> bool:
        return overview_option.title in {"Learning words", "Mature words"}
