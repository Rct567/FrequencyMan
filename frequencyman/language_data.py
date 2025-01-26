"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from collections import defaultdict
import csv
from typing import Iterator, NewType, Optional

from .lib.utilities import *
from .text_processing import TextProcessing, LangId
import os

LangDataId = NewType('LangDataId', str)  # full lowercased string of specified language of field


class WordFrequencyLists:

    data_dir: str
    word_frequency_lists: Optional[dict[LangDataId, dict[str, float]]]

    def __init__(self, root_dir: str) -> None:

        self.data_dir = root_dir
        self.word_frequency_lists = None

    def get_files_by_id(self, lang_data_id: LangDataId) -> set[str]:

        possible_lang_dir = os.path.join(self.data_dir, lang_data_id)

        files: set[str] = set()

        if os.path.isdir(possible_lang_dir):
            for file_name in os.listdir(possible_lang_dir):
                if not file_name.endswith('.txt') and not file_name.endswith('.csv'):
                    continue
                if file_name.startswith('ignore'):
                    continue
                files.add(os.path.join(possible_lang_dir, file_name))

        return files

    def id_has_list_file(self, lang_data_id: LangDataId) -> bool:

        return len(self.get_files_by_id(lang_data_id)) > 0

    def __list_already_loaded(self, lang_data_id: LangDataId) -> bool:

        return self.word_frequency_lists is not None and lang_data_id in self.word_frequency_lists

    def load_lists(self, lang_data_ids: set[LangDataId]) -> None:

        for lang_data_id in lang_data_ids:
            self.__load_list(lang_data_id)

    def __load_list(self, lang_data_id: LangDataId) -> None:

        if self.__list_already_loaded(lang_data_id):
            return

        files = self.get_files_by_id(lang_data_id)

        if self.word_frequency_lists is None:
            self.word_frequency_lists = {}

        self.word_frequency_lists[lang_data_id] = WordFrequencyLists.__produce_combined_list(files, lang_data_id)


    @staticmethod
    def combine_lists_by_top_position(lists: Iterable[Iterable[tuple[str, int]]]) -> dict[str, int]:

        words_positions_combined: dict[str, int] = {}

        for word_list in lists:
            for word, line_number in word_list:
                assert line_number > 0
                if word not in words_positions_combined or line_number < words_positions_combined[word]:
                    words_positions_combined[word] = line_number

        return words_positions_combined

    @staticmethod
    def combine_lists_by_avg_position(wf_lists: Iterable[Iterable[tuple[str, int]]]) -> dict[str, int]:

        word_positions: dict[str, list[int]] = defaultdict(list)
        wf_list_num = 0
        lowest_position = 0

        for wf_list in wf_lists:
            for word, line_number in wf_list:
                assert line_number > 0
                word_positions[word].append(line_number)
                if line_number > lowest_position:
                    lowest_position = line_number
            wf_list_num += 1

        for word, positions in word_positions.items():
            if len(positions) < wf_list_num:
                #word_positions[word].extend([ int(mean(positions)*2.5) for _ in range(wf_list_num-len(positions)) ])
                word_positions[word].extend([ lowest_position+1 for _ in range(wf_list_num-len(positions)) ])

        combined_positions: dict[str, float] = {word: sum(positions) / len(positions) for word, positions in word_positions.items()}
        combined_positions = dict(sorted(combined_positions.items(), key=lambda item: item[1]))
        return {word: int(position) for word, position in combined_positions.items()}


    @staticmethod
    def __produce_combined_list(files: set[str], lang_data_id: LangDataId) -> dict[str, float]:

        lang_id = LanguageData.get_lang_id_from_data_id(lang_data_id)
        words_positions_combined = WordFrequencyLists.combine_lists_by_top_position((WordFrequencyLists.get_words_from_file(file_path, lang_id) for file_path in files))

        if not words_positions_combined:
            return {}

        words_positions_combined = sort_dict_floats_values({word: 1/line_number for word, line_number in words_positions_combined.items()})
        words_positions_combined = normalize_dict_positional_floats_values(words_positions_combined)

        return words_positions_combined


    @staticmethod
    def get_words_from_file(file_path: str, lang_id: LangId) -> Iterator[tuple[str, int]]:

        with open(file_path, encoding='utf-8') as text_file:
            for word, line_number in WordFrequencyLists.get_words_from_content(text_file, file_path, lang_id):
                yield word, line_number


    @staticmethod
    def get_words_from_content(content:Iterable[str], file_path: str, lang_id: LangId) -> Iterator[tuple[str, int]]:

        line_number = 1
        is_csv_file = file_path.endswith('.csv')
        is_acceptable_word = TextProcessing.get_word_accepter(lang_id)

        if is_csv_file:
            delimiter = ','
        else:
            delimiter = ' '

        reader = csv.reader(content, delimiter=delimiter)
        word_column_index = 0

        for line in reader:

            if line_number == 1 and len(line) > 1:
                if line[1] == 'Morph-Inflection':
                    word_column_index = 1
                if any(column.lower() in {'frequency', 'freq', 'ngram', 'word', 'count'} for column in line):
                    continue

            word = line[word_column_index]
            word = word.strip().lower()

            if is_acceptable_word(word):
                yield word, line_number
                line_number += 1


class IgnoreLists:

    data_dir: str
    ignore_lists: Optional[dict[LangDataId, set[str]]]

    def __init__(self, lang_data_dir: str) -> None:

        self.data_dir = lang_data_dir
        self.ignore_lists = None

    def load_lists(self, lang_data_ids: set[LangDataId]) -> None:

        for lang_data_id in lang_data_ids:
            self.__load_list(lang_data_id)

    def __load_list(self, lang_data_id: LangDataId) -> None:

        if self.__list_already_loaded(lang_data_id):
            return

        files = self.get_files_by_id(lang_data_id)

        if self.ignore_lists is None:
            self.ignore_lists = {}

        self.ignore_lists[lang_data_id] = self.__produce_combined_list(files)

    def id_has_list_file(self, lang_data_id: LangDataId) -> bool:

        return len(self.get_files_by_id(lang_data_id)) > 0

    def get_files_by_id(self, lang_data_id: LangDataId) -> set[str]:

        possible_lang_dir = os.path.join(self.data_dir, lang_data_id)

        files: set[str] = set()

        if os.path.isdir(possible_lang_dir):
            for file_name in os.listdir(possible_lang_dir):
                if not file_name.endswith('.txt'):
                    continue
                if not file_name.startswith('ignore'):
                    continue

                files.add(os.path.join(possible_lang_dir, file_name))

        return files

    def __produce_combined_list(self, files: set[str]) -> set[str]:

        ignore_list_combined: set[str] = set()

        for file_path in files:
            for word in self.get_words_from_file(file_path):
                ignore_list_combined.add(word)

        return ignore_list_combined

    @staticmethod
    def get_words_from_file(file_path: str) -> Iterator[str]:

        with open(file_path, encoding='utf-8') as text_file:

            for line in text_file:
                line = line.rstrip()
                word = line.strip().lower()
                yield word

    def __list_already_loaded(self, lang_data_id: LangDataId) -> bool:

        return self.ignore_lists is not None and lang_data_id in self.ignore_lists


class NamesLists:

    lang_data_dir: str
    names_lists: Optional[list[set[str]]]
    names_list: Optional[set[str]]

    def __init__(self, lang_data_dir: str) -> None:

        self.lang_data_dir = lang_data_dir
        self.names_lists = None
        self.names_list = None

    def __get_files(self) -> set[str]:

        files: set[str] = set()

        if os.path.isdir(self.lang_data_dir):
            for file_name in os.listdir(self.lang_data_dir):
                if not file_name.endswith('.txt'):
                    continue
                if not file_name.startswith('names'):
                    continue

                files.add(os.path.join(self.lang_data_dir, file_name))

        return files

    def load_lists(self) -> None:

        if self.names_list is not None and self.names_lists is not None:
            return

        self.names_list = set()
        self.names_lists = []

        for names_file in self.__get_files():
            self.__load_list(names_file)

    def __load_list(self, names_file: str) -> None:

        assert self.names_list is not None and self.names_lists is not None

        words = set(IgnoreLists.get_words_from_file(names_file))

        self.names_list.update(words)
        self.names_lists.append(words)

        self.lists_loaded = True


class LanguageData:

    data_dir: str
    word_frequency_lists: WordFrequencyLists
    ignore_lists: IgnoreLists
    names_lists: NamesLists

    def __init__(self, lang_data_dir: str) -> None:

        if not os.path.isdir(lang_data_dir):
            raise ValueError("Invalid 'language data' directory. Directory not found: "+lang_data_dir)

        self.data_dir = lang_data_dir
        self.word_frequency_lists = WordFrequencyLists(self.data_dir)
        self.ignore_lists = IgnoreLists(self.data_dir)
        self.names_lists = NamesLists(self.data_dir)

    def id_has_directory(self, lang_data_id: LangDataId) -> bool:

        if lang_data_id == "":
            return False

        possible_lang_dir = os.path.join(self.data_dir, lang_data_id)
        return os.path.isdir(possible_lang_dir)

    def load_data(self, lang_data_ids: set[LangDataId]) -> None:

        self.word_frequency_lists.load_lists(lang_data_ids)
        self.ignore_lists.load_lists(lang_data_ids)
        self.names_lists.load_lists()

    def get_word_frequency(self, lang_data_id: LangDataId, word: str, default: float) -> float:

        if self.word_frequency_lists.word_frequency_lists is None:
            raise Exception("No word frequency lists loaded.")

        try:
            return self.word_frequency_lists.word_frequency_lists[lang_data_id][word]
        except KeyError:
            return default

    def get_ignore_list(self, lang_data_id: LangDataId) -> set[str]:

        if self.ignore_lists.ignore_lists is None:
            raise Exception("No ignore lists loaded.")

        try:
            return self.ignore_lists.ignore_lists[lang_data_id]
        except KeyError:
            return set()

    def get_names_list(self) -> set[str]:

        if self.names_lists.names_list is None:
            raise Exception("No names list loaded.")

        return self.names_lists.names_list

    def get_ignored_words(self, lang_data_id: LangDataId) -> set[str]:

        return self.get_ignore_list(lang_data_id).union(self.get_names_list())

    @staticmethod
    def get_lang_id_from_data_id(lang_data_id: LangDataId) -> LangId:

        if (len(lang_data_id) > 3 and lang_data_id[2] == '_'):
            return LangId(lang_data_id[:2])

        return LangId(lang_data_id)
