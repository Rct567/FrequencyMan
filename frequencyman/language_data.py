"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from typing import Iterator, NewType, Optional

from .lib.utilities import *
from .text_processing import TextProcessing
import os

LangDataId = NewType('LangDataKey', str)  # full lowercased string of specified language of field
LangId = NewType('LangId', str)  # first part of lang_key (en/jp/sp)


class LanguageData:

    lang_data_dir: str
    word_frequency_lists: Optional[dict[LangDataId, dict[str, float]]]

    def __init__(self, lang_data_dir_pointer) -> None:

        lang_data_dir = os.path.join(lang_data_dir_pointer, 'lang_data')

        if not os.path.isdir(lang_data_dir):
            raise ValueError("Invalid 'language data' directory. Directory not found: "+lang_data_dir)
        self.lang_data_dir = lang_data_dir
        self.word_frequency_lists = None

    def get_word_frequency(self, key: LangDataId, word: str, default: float):

        if self.word_frequency_lists is None:
            raise Exception("No word frequency lists loaded.")
        try:
            return self.word_frequency_lists[key][word]
        except KeyError:
            return default

    def str_key_has_frequency_list_file(self, key: str) -> bool:

        return self.key_has_frequency_list_file(LangDataId(key))

    def key_has_frequency_list_file(self, key: LangDataId) -> bool:

        return len(self.__get_frequency_list_files_for_lang_key(key)) > 0

    def keys_have_frequency_list_file(self, keys: list[LangDataId]) -> bool:

        for key in keys:
            if not self.key_has_frequency_list_file(key):
                return False
        return True

    def __get_frequency_list_files_for_lang_key(self, key: LangDataId) -> list[str]:

        key_str = key.lower()
        possible_dir = os.path.join(self.lang_data_dir, key_str)

        files = []

        if os.path.isdir(possible_dir):
            for file_name in os.listdir(possible_dir):
                if not file_name.endswith('.txt'):
                    continue
                files.append(os.path.join(possible_dir, file_name))
        return files

    def __word_frequency_list_already_loaded(self, key: LangDataId) -> bool:

        return self.word_frequency_lists is not None and key in self.word_frequency_lists

    def load_frequency_lists(self, keys: list[LangDataId]) -> None:

        for key in keys:
            self.__load_word_frequency_list(key)

    def __load_word_frequency_list(self, key: LangDataId) -> None:

        if self.__word_frequency_list_already_loaded(key):
            return

        files = self.__get_frequency_list_files_for_lang_key(key)

        if len(files) < 1:
            raise ValueError(f"No word frequency list file found for key '{key}'.")

        if self.word_frequency_lists is None:
            self.word_frequency_lists = {}

        self.word_frequency_lists[key] = self.__produce_word_frequency_list(files)

    def __produce_word_frequency_list(self, files: list[str]) -> dict[str, float]:

        all_files_word_rankings_combined: dict[str, int] = {}

        for file_path in files:
            if not file_path.endswith('.txt'):
                continue

            for word, line_number in self.__get_words_from_word_frequency_file(file_path):
                if word not in all_files_word_rankings_combined or line_number < all_files_word_rankings_combined[word]:  # highest ranking among lists (lowest line number)
                    all_files_word_rankings_combined[word] = line_number

        if not all_files_word_rankings_combined:
            return {}

        max_rank = max(all_files_word_rankings_combined.values())
        return {word: (max_rank-(ranking-1))/max_rank for (word, ranking) in all_files_word_rankings_combined.items()}

    def __get_words_from_word_frequency_file(self, file_path: str) -> Iterator[tuple[str, int]]:

        line_number = 1

        with open(file_path, encoding='utf-8') as text_file:

            for line in text_file:
                line = line.rstrip()
                last_space_index = line.rfind(' ')
                if last_space_index != -1 and last_space_index < len(line) - 1 and line[last_space_index + 1:].isdigit():
                    word = line[:last_space_index]
                else:
                    word = line
                word = word.strip().lower()
                if TextProcessing.acceptable_word(word):
                    yield word, line_number
                    line_number += 1
