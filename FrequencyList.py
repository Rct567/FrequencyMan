from io import TextIOWrapper
import re
from typing import Dict
import os

def load_word_frequency_list(file_or_directory: str) -> Dict[str, float]:
    word_rankings: Dict[str, list[int]] = {}
    word_rankings_combined: Dict[str, int] = {}

    if os.path.isdir(file_or_directory):
        for file_name in os.listdir(file_or_directory):
            if not file_name.endswith('.txt'):
                continue
            with open(os.path.join(file_or_directory, file_name), encoding='utf-8') as file:
                load_word_rankings_from_file(file, word_rankings)
    else:
        with open(file_or_directory, encoding='utf-8') as file:
            load_word_rankings_from_file(file, word_rankings)

    for word, rankings in word_rankings.items():
        # word_rankings_combined[word] = sum(rankings) / len(rankings)
        word_rankings_combined[word] = max(rankings)

    max_rank = max(word_rankings_combined.values())
    return {word: (max_rank-(ranking-1))/max_rank for (word, ranking) in word_rankings_combined.items()}


def load_word_rankings_from_file(file: TextIOWrapper, all_files_word_rankings: Dict[str, list[int]]) -> None:
    word_pattern = re.compile(r'\w{2,}', re.UNICODE)
    file_word_rankings: list[str] = []

    for line in file:
        word = line.strip().lower()
        if word not in file_word_rankings and len(word) > 1 and len(word) < 300 and re.search(word_pattern, word):
            file_word_rankings.append(word)
               
    for index, word in enumerate(file_word_rankings):
        ranking = index+1
        if word in all_files_word_rankings:
            all_files_word_rankings[word].append(ranking)
        else:
            all_files_word_rankings[word] = [ranking]

# Example usage:
result = load_word_frequency_list('user_files/frequency_lists/en/')
print(result)