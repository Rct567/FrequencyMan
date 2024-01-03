"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from typing import Iterator, NewType, Optional

from .lib.utilities import *
from .text_processing import TextProcessing
import os

LangKey = NewType('LangKey', str)  # full lowercased string of specified language of field
LangId = NewType('LangId', str)  # first part of lang_key (en/jp/sp)


class WordFrequencyLists:

    list_dir: str
    word_frequency_lists: dict[LangKey, dict[str, float]]

    def __init__(self, list_dir) -> None:
        if not os.path.isdir(list_dir):
            raise ValueError("Invalid 'word frequency list' directory. Directory not found: "+list_dir)
        self.list_dir = list_dir
        self.word_frequency_lists = {}

    def __getitem__(self, key: LangKey):
        self.require_loaded_lists(key)
        return self.word_frequency_lists[key]

    def __contains__(self, key: LangKey):
        self.require_loaded_lists(key)
        return key in self.word_frequency_lists

    def get(self, key: LangKey, default=None):
        self.require_loaded_lists(key)
        return self.word_frequency_lists.get(key, default)

    def get_word_frequency(self, key: LangKey, word: str, default: float):
        self.require_loaded_lists(key)
        return self.word_frequency_lists[key].get(word, default)

    def require_loaded_lists(self, key: Optional[LangKey] = None) -> None:
        if (len(self.word_frequency_lists) < 1):
            raise Exception("No word frequency lists loaded.")
        if key is not None and key not in self.word_frequency_lists:
            raise Exception("Word frequency list '{}' not loaded.".format(key))

    def str_key_has_frequency_list_file(self, key: str) -> bool:
        return self.key_has_frequency_list_file(LangKey(key))

    def key_has_frequency_list_file(self, key: LangKey) -> bool:
        return len(self.__get_files_for_lang_key(key)) > 0

    def keys_have_frequency_list_file(self, keys: list[LangKey]) -> bool:
        for key in keys:
            if not self.key_has_frequency_list_file(key):
                return False
        return True

    def __get_files_for_lang_key(self, key: LangKey) -> list[str]:
        key_str = key.lower()
        possible_file = os.path.join(self.list_dir, key_str+".txt")
        possible_dir = os.path.join(self.list_dir, key_str)

        files = []

        if os.path.isfile(possible_file):
            files.append(possible_file)
        elif os.path.isdir(possible_dir):
            for file_name in os.listdir(possible_dir):
                if not file_name.endswith('.txt'):
                    continue
                files.append(os.path.join(possible_dir, file_name))
        return files

    def __list_already_loaded(self, key: LangKey) -> bool:
        return key in self.word_frequency_lists

    def load_frequency_lists(self, keys: list[LangKey]) -> None:
        for key in keys:
            self.__load_frequency_list(key)

    def __load_frequency_list(self, key: LangKey) -> None:
        if self.__list_already_loaded(key):
            return

        files = self.__get_files_for_lang_key(key)

        if len(files) < 1:
            raise ValueError(f"No word frequency list found for key '{key}'.")

        self.word_frequency_lists[key] = self.__produce_word_frequency_list(files)

    def __produce_word_frequency_list(self, files: list[str]) -> dict[str, float]:

        all_files_word_rankings_combined: dict[str, int] = {}

        for file_path in files:
            if not file_path.endswith('.txt'):
                continue

            for word, line_number in self.__get_word_rankings_from_file(file_path):
                if word not in all_files_word_rankings_combined or line_number < all_files_word_rankings_combined[word]:  # highest ranking among lists (lowest line number)
                    all_files_word_rankings_combined[word] = line_number

        if not all_files_word_rankings_combined:
            return {}

        max_rank = max(all_files_word_rankings_combined.values())
        return {word: (max_rank-(ranking-1))/max_rank for (word, ranking) in all_files_word_rankings_combined.items()}

    def __get_word_rankings_from_file(self, file_path: str) -> Iterator[tuple[str, int]]:

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
