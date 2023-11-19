from io import TextIOWrapper
from typing import NewType, Optional

from .lib.utilities import *
from .text_processing import TextProcessing
import os

LangKey = NewType('LangKey', str)  # full lowercased string of specified language of field
LangId = NewType('LangId', str)  # first part of lang_key (en/jp/sp)


class WordFrequencyList:
    def __init__(self):
        pass


class WordFrequencyLists:

    list_dir: str
    word_frequency_lists: dict[LangKey, dict[str, float]] = {}

    def __init__(self, list_dir) -> None:
        if not os.path.isdir(list_dir):
            raise ValueError("Invalid 'word frequency list' directory. Directory not found: "+list_dir)
        self.list_dir = list_dir

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

    def already_loaded(self, key: LangKey) -> bool:
        return key in self.word_frequency_lists

    def require_loaded_lists(self, key: Optional[LangKey] = None) -> None:
        if (len(self.word_frequency_lists) < 1):
            raise Exception("No word frequency lists loaded.")
        if key is not None:
            if key not in self.word_frequency_lists:
                raise Exception(f"Word frequency list '{key}' not loaded.")
            if (len(self.word_frequency_lists[key]) < 1):
                raise Exception(f"Word frequency list '{key}' not loaded.")

    def load_frequency_lists(self, keys: list[LangKey]) -> None:
        for key in keys:
            self.load_frequency_list(key)

    def key_has_frequency_list_file(self, key: LangKey) -> bool:
        return len(self.get_files_for_lang_key(key)) > 0

    def keys_have_frequency_list_file(self, keys: list[LangKey]) -> bool:
        for key in keys:
            if not self.key_has_frequency_list_file(key):
                return False
        return True

    def get_files_for_lang_key(self, key: LangKey) -> list[str]:
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

    def load_frequency_list(self, key: LangKey) -> None:
        if self.already_loaded(key):
            return

        files = self.get_files_for_lang_key(key)

        if len(files) < 1:
            raise ValueError(f"No word frequency list found for key '{key}'.")

        self.word_frequency_lists[key] = self.__produce_word_frequency_list(files)

    def __produce_word_frequency_list(self, files: list[str]) -> dict[str, float]:

        all_files_word_rankings: dict[str, list[int]] = {}
        all_files_word_rankings_combined: dict[str, int] = {}

        for file_name in files:
            if not file_name.endswith('.txt'):
                continue
            with open(os.path.join(file_name, file_name), encoding='utf-8') as file:
                self.__set_word_rankings_from_file(file, all_files_word_rankings) # adds to all_files_word_rankings

        for word, rankings in all_files_word_rankings.items():
            all_files_word_rankings_combined[word] = min(rankings)  # highest ranking among lists (lowest int / line number)

        max_rank = max(all_files_word_rankings_combined.values())
        return {word: (max_rank-(ranking-1))/max_rank for (word, ranking) in all_files_word_rankings_combined.items()}

    def __set_word_rankings_from_file(self, file: TextIOWrapper, all_files_word_rankings: dict[str, list[int]]) -> None:

        file_word_rankings: list[str] = []

        for line in file:
            word = line.strip().lower()
            if word not in file_word_rankings and TextProcessing.acceptable_word(word):
                file_word_rankings.append(word)

        for index, word in enumerate(file_word_rankings):
            ranking = index+1
            if word in all_files_word_rankings:
                all_files_word_rankings[word].append(ranking)
            else:
                all_files_word_rankings[word] = [ranking]
