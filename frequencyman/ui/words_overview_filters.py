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


TableDataType = list[tuple[WordToken, list[Union[float, int]]]]


class FilterOption(ABC):

    title: str

    @abstractmethod
    def filter_data(self, data: TableDataType, metrics: SegmentContentMetrics) -> TableDataType:
        pass

    @abstractmethod
    def is_enabled(self, data: TableDataType, metrics: SegmentContentMetrics) -> bool:
        pass

    @abstractmethod
    def is_hidden(self, overview_option: WordsOverviewOption, metrics: SegmentContentMetrics) -> bool:
        pass


class MatureWordsFilter(FilterOption):

    title = "Mature words"

    @override
    def filter_data(self, data: TableDataType, metrics: SegmentContentMetrics) -> TableDataType:
        return [row for row in data if isinstance(row[0], str) and row[0] in metrics.mature_words]

    @override
    def is_enabled(self, data: TableDataType, metrics: SegmentContentMetrics) -> bool:
        return any(row for row in data if isinstance(row[0], str) and row[0] in metrics.mature_words)

    @override
    def is_hidden(self, overview_option: WordsOverviewOption, metrics: SegmentContentMetrics) -> bool:
        return overview_option.title in {"Learning words", "Mature words"}


class LearningWordsFilter(FilterOption):

    title = "Learning words"

    @override
    def filter_data(self, data: TableDataType, metrics: SegmentContentMetrics) -> TableDataType:
        return [row for row in data if isinstance(row[0], str) and row[0] in metrics.words_familiarity and row[0] not in metrics.mature_words]

    @override
    def is_enabled(self, data: TableDataType, metrics: SegmentContentMetrics) -> bool:
        return any(row for row in data if isinstance(row[0], str) and row[0] in metrics.words_familiarity and row[0] not in metrics.mature_words)

    @override
    def is_hidden(self, overview_option: WordsOverviewOption, metrics: SegmentContentMetrics) -> bool:
        return overview_option.title in {"Learning words", "Mature words"}


class IgnoredWordsFilter(FilterOption):

    title = "Ignored words"

    @override
    def filter_data(self, data: TableDataType, metrics: SegmentContentMetrics) -> TableDataType:
        return [row for row in data if isinstance(row[0], str) and row[0] in metrics.ignored_words]

    @override
    def is_enabled(self, data: TableDataType, metrics: SegmentContentMetrics) -> bool:
        return any(row for row in data if isinstance(row[0], str) and row[0] in metrics.ignored_words)

    @override
    def is_hidden(self, overview_option: WordsOverviewOption, metrics: SegmentContentMetrics) -> bool:
        return overview_option.title in {"Ignored words"} or not metrics.ignored_words
