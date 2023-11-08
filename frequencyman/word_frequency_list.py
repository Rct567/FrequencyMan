from io import TextIOWrapper
import re
from typing import Dict

from .lib.utilities import *
from .text_processing import TextProcessing
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
        self.require_loaded_lists(key)
        return self.word_frequency_lists[key]
     
    def __contains__(self, key:str):
        self.require_loaded_lists(key)
        return key in self.word_frequency_lists
    
    def get(self, key:str, default=None):
        self.require_loaded_lists(key)
        return self.word_frequency_lists.get(key, default)
    
    def get_word_frequency(self, key:str, word:str, default:float):
        self.require_loaded_lists(key)
        return self.word_frequency_lists[key].get(word, default)
    
    def already_loaded(self, key:str) -> bool:
        return key in self.word_frequency_lists
    
    def require_loaded_lists(self, key=None) -> None:
        if (len(self.word_frequency_lists) < 1):
            raise Exception("No word frequency lists loaded.")
        if key is not None:
            if key not in self.word_frequency_lists:
                raise Exception(f"Word frequency list '{key}' not loaded.")
            if (len(self.word_frequency_lists[key]) < 1):
                raise Exception(f"Word frequency list '{key}' not loaded.")
            
    
    def load_frequency_lists(self, keys:list[str]) -> None:
        for key in keys:
            self.load_frequency_list(key)
            
    def key_has_frequency_list_file(self, key:str) -> bool: 
        return len(self.get_files_for_lang_key(key)) > 0
       
    def keys_have_frequency_list_file(self, keys:list[str]) -> bool:
        for key in keys:
            if not self.key_has_frequency_list_file(key):
                return False
        return True
      
    def get_files_for_lang_key(self, key:str) -> list[str]:
        key = key.lower()
        possible_file = os.path.join(self.list_dir, key+".txt")
        possible_dir = os.path.join(self.list_dir, key)
        
        files = []
        
        if os.path.isfile(possible_file):
            files.append(possible_file)
        elif os.path.isdir(possible_dir):
            for file_name in os.listdir(possible_dir):
                if not file_name.endswith('.txt'):
                    continue
                files.append(os.path.join(possible_dir, file_name))   
        return files
        
    
    def load_frequency_list(self, key:str) -> bool:
        if self.already_loaded(key):
            return True
        
        files = self.get_files_for_lang_key(key)
        
        if len(files) < 1:
            raise ValueError(f"No word frequency list found for key '{key}'.")
        
        word_frequency_list = self.load_word_frequency_list(files)
        self.word_frequency_lists[key] = word_frequency_list;
        return True
    

    def load_word_frequency_list(self, files: list[str]) -> Dict[str, float]:
        word_rankings: Dict[str, list[int]] = {}
        word_rankings_combined: Dict[str, int] = {}

        for file_name in files:
            if not file_name.endswith('.txt'):
                continue
            with open(os.path.join(file_name, file_name), encoding='utf-8') as file:
                self.load_word_rankings_from_file(file, word_rankings)

        for word, rankings in word_rankings.items():
            # word_rankings_combined[word] = sum(rankings) / len(rankings)
            word_rankings_combined[word] = min(rankings) # highest position

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
