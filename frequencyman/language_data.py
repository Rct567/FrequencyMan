"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from typing import Iterator, NewType, Optional

from .lib.utilities import *
from .text_processing import TextProcessing, LangId
import os

LangDataId = NewType('LangDataId', str)  # full lowercased string of specified language of field

class LanguageData:

    root_dir: str
    word_frequency_lists: Optional[dict[LangDataId, dict[str, float]]]

    def __init__(self, lang_data_parent_dir) -> None:

        lang_data_dir = os.path.join(lang_data_parent_dir, 'lang_data')

        if not os.path.isdir(lang_data_dir):
            raise ValueError("Invalid 'language data' directory. Directory not found: "+lang_data_dir)

        self.root_dir = lang_data_dir
        self.word_frequency_lists = None

    def get_word_frequency(self, lang_data_id: LangDataId, word: str, default: float):

        if self.word_frequency_lists is None:
            raise Exception("No word frequency lists loaded.")
        try:
            return self.word_frequency_lists[lang_data_id][word]
        except KeyError:
            return default

    def id_has_word_frequency_list(self, lang_data_id: LangDataId) -> bool:

        return len(self.__get_word_frequency_list_files_by_id(lang_data_id)) > 0

    def id_has_directory(self, lang_data_id: LangDataId) -> bool:

        possible_lang_dir = os.path.join(self.root_dir, lang_data_id)
        return os.path.isdir(possible_lang_dir)

    @staticmethod
    def get_lang_id_from_data_id(lang_data_id: LangDataId) -> LangId:

        if (len(lang_data_id) > 3 and lang_data_id[2] == '_'):
            return LangId(lang_data_id[:2])
        return LangId(lang_data_id)

    def all_ids_have_word_frequency_list(self, lang_data_ids: list[LangDataId]) -> bool:

        for lang_data_id in lang_data_ids:
            if not self.id_has_word_frequency_list(lang_data_id):
                return False
        return True

    def __get_word_frequency_list_files_by_id(self, lang_data_id: LangDataId) -> list[str]:

        possible_lang_dir = os.path.join(self.root_dir, lang_data_id)

        files = []

        if os.path.isdir(possible_lang_dir):
            for file_name in os.listdir(possible_lang_dir):
                if not file_name.endswith('.txt'):
                    continue
                files.append(os.path.join(possible_lang_dir, file_name))

        return files

    def __word_frequency_list_already_loaded(self, id: LangDataId) -> bool:

        return self.word_frequency_lists is not None and id in self.word_frequency_lists

    def load_word_frequency_lists(self, lang_data_ids: list[LangDataId]) -> None:

        for lang_data_id in lang_data_ids:
            self.__load_word_frequency_list(lang_data_id)

    def __load_word_frequency_list(self, lang_data_id: LangDataId) -> None:

        if self.__word_frequency_list_already_loaded(lang_data_id):
            return

        files = self.__get_word_frequency_list_files_by_id(lang_data_id)

        if len(files) < 1:
            raise ValueError(f"No word frequency list file found for lang_data_id '{lang_data_id}'.")

        if self.word_frequency_lists is None:
            self.word_frequency_lists = {}

        self.word_frequency_lists[lang_data_id] = self.__produce_word_frequency_list(files)

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
