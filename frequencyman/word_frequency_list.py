from io import TextIOWrapper
import re
from typing import Dict
from ..frequencyman.text_processing import TextProcessing
import os

class WordFrequencyList:
    def __init__(self):
        pass
    

class WordFrequencyLists:
    
    list_dir:str
    word_frequency_lists:dict[str, dict[str, float]] = {}
    
    def __init__(self, list_dir) -> None:
        if not os.path.isdir(list_dir):
            raise ValueError("Invalid 'word frequency list' directory. Directory not found: "+list_dir)
        self.list_dir = list_dir
    
    def __getitem__(self, key:str):
        self.load_frequency_list_if_needed(key)
        return self.word_frequency_lists[key]
     
    def __contains__(self, key:str):
        self.load_frequency_list_if_needed(key)
        return key in self.word_frequency_lists
    
    def get(self, key:str, default=None):
        self.load_frequency_list_if_needed(key)
        return self.word_frequency_lists.get(key, default)
    
    def getWordFrequency(self, key:str, word:str, default:float):
        self.load_frequency_list_if_needed(key)
        return self.word_frequency_lists[key].get(word, default)
    
    def alreadyLoaded(self, key:str):
        return key in self.word_frequency_lists
    
    def load_frequency_list_if_needed(self, key:str) -> bool:
        if self.alreadyLoaded(key):
            return True
        
        key = key.lower()
        possible_file = os.path.join(self.list_dir, key+".txt")
        possible_dir = os.path.join(self.list_dir, key)
        
        if os.path.isfile(possible_file):
            file_or_dir = possible_file
        elif os.path.isdir(possible_dir):
            file_or_dir = possible_dir
        else:
            raise ValueError(f"Not word frequency list found for key '{key}'.")
        
        word_frequency_list = self.load_word_frequency_list(file_or_dir)
        self.word_frequency_lists[key] = word_frequency_list;
        return True
    

    def load_word_frequency_list(self, file_or_directory: str) -> Dict[str, float]:
        word_rankings: Dict[str, list[int]] = {}
        word_rankings_combined: Dict[str, int] = {}

        if os.path.isdir(file_or_directory):
            for file_name in os.listdir(file_or_directory):
                if not file_name.endswith('.txt'):
                    continue
                with open(os.path.join(file_or_directory, file_name), encoding='utf-8') as file:
                    self.load_word_rankings_from_file(file, word_rankings)
        else:
            with open(file_or_directory, encoding='utf-8') as file:
                self.load_word_rankings_from_file(file, word_rankings)

        for word, rankings in word_rankings.items():
            # word_rankings_combined[word] = sum(rankings) / len(rankings)
            word_rankings_combined[word] = max(rankings)

        max_rank = max(word_rankings_combined.values())
        return {word: (max_rank-(ranking-1))/max_rank for (word, ranking) in word_rankings_combined.items()}


    def load_word_rankings_from_file(self, file: TextIOWrapper, all_files_word_rankings: Dict[str, list[int]]) -> None:
        
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

