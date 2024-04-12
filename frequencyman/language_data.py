"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

import re
from typing import Iterator, NewType, Optional

from .lib.utilities import *
from .text_processing import TextProcessing, LangId
import os

LangDataId = NewType('LangDataId', str)  # full lowercased string of specified language of field


class WordFrequencyLists:

    root_dir: str
    word_frequency_lists: Optional[dict[LangDataId, dict[str, float]]]

    def __init__(self, root_dir: str) -> None:

        self.root_dir = root_dir
        self.word_frequency_lists = None

    def get_files_by_id(self, lang_data_id: LangDataId) -> set[str]:

        possible_lang_dir = os.path.join(self.root_dir, lang_data_id)

        files = set()

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

        self.word_frequency_lists[lang_data_id] = self.__produce_combined_list(files, lang_data_id)

    def __produce_combined_list(self, files: set[str], lang_data_id: LangDataId) -> dict[str, float]:

        word_rankings_combined: dict[str, int] = {}
        lang_id = LanguageData.get_lang_id_from_data_id(lang_data_id)

        for file_path in files:
            for word, line_number in self.__get_words_from_file(file_path, lang_id):
                if word not in word_rankings_combined or line_number < word_rankings_combined[word]:  # highest ranking among lists (lowest line number)
                    word_rankings_combined[word] = line_number

        if not word_rankings_combined:
            return {}

        max_rank = max(word_rankings_combined.values())
        return {word: (max_rank-(ranking-1))/max_rank for (word, ranking) in word_rankings_combined.items()}

    @staticmethod
    def __get_words_from_file(file_path: str, lang_id: LangId) -> Iterator[tuple[str, int]]:

        line_number = 1
        is_csv_file = file_path.endswith('.csv')
        csv_patters = re.compile(r'(?:^|,)(?=[^"]|(")?)"?([^",]*)"?(")?,(?:.|$)')

        with open(file_path, encoding='utf-8') as text_file:
            for line in text_file:
                if is_csv_file:
                    if line_number == 1 and 'freq' in line:
                        continue
                    first_column = re.match(csv_patters, line)
                    if first_column:
                        word = first_column.group(2)
                    else:
                        continue
                else:
                    line = line.rstrip()
                    last_space_index = line.rfind(' ')
                    if last_space_index != -1 and last_space_index < len(line) - 1 and line[last_space_index + 1:].isdigit():
                        word = line[:last_space_index]
                    else:
                        word = line

                word = word.strip().lower()
                if TextProcessing.acceptable_word(word, lang_id):
                    yield word, line_number
                    line_number += 1


class IgnoreLists:

    root_dir: str
    ignore_lists: Optional[dict[LangDataId, set[str]]]

    def __init__(self, root_dir: str) -> None:

        self.root_dir = root_dir
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

        possible_lang_dir = os.path.join(self.root_dir, lang_data_id)

        files = set()

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
            for word in self.__get_words_from_file(file_path):
                ignore_list_combined.add(word)

        return ignore_list_combined

    @staticmethod
    def __get_words_from_file(file_path: str) -> Iterator[str]:

        with open(file_path, encoding='utf-8') as text_file:

            for line in text_file:
                line = line.rstrip()
                word = line.strip().lower()
                yield word

    def __list_already_loaded(self, lang_data_id: LangDataId) -> bool:

        return self.ignore_lists is not None and lang_data_id in self.ignore_lists


class LanguageData:

    root_dir: str
    word_frequency_lists: WordFrequencyLists
    ignore_lists: IgnoreLists

    def __init__(self, lang_data_parent_dir) -> None:

        lang_data_dir = os.path.join(lang_data_parent_dir, 'lang_data')

        if not os.path.isdir(lang_data_dir):
            raise ValueError("Invalid 'language data' directory. Directory not found: "+lang_data_dir)

        self.root_dir = lang_data_dir
        self.word_frequency_lists = WordFrequencyLists(self.root_dir)
        self.ignore_lists = IgnoreLists(self.root_dir)

    def id_has_directory(self, lang_data_id: LangDataId) -> bool:

        if lang_data_id == "":
            return False

        possible_lang_dir = os.path.join(self.root_dir, lang_data_id)
        return os.path.isdir(possible_lang_dir)

    def load_data(self, lang_data_ids: set[LangDataId]) -> None:

        self.word_frequency_lists.load_lists(lang_data_ids)
        self.ignore_lists.load_lists(lang_data_ids)

    def get_word_frequency(self, lang_data_id: LangDataId, word: str, default: float) -> float:

        if self.word_frequency_lists.word_frequency_lists is None:
            raise Exception("No word frequency lists loaded.")

        try:
            return self.word_frequency_lists.word_frequency_lists[lang_data_id][word]
        except KeyError:
            return default

    def is_ignore_word(self, lang_data_id: LangDataId, word: str) -> bool:

        if self.ignore_lists.ignore_lists is None:
            raise Exception("No ignore lists loaded.")

        try:
            return word in self.ignore_lists.ignore_lists[lang_data_id]
        except KeyError:
            return False

    @staticmethod
    def get_lang_id_from_data_id(lang_data_id: LangDataId) -> LangId:

        if (len(lang_data_id) > 3 and lang_data_id[2] == '_'):
            return LangId(lang_data_id[:2])

        return LangId(lang_data_id)
