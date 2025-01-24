import os
import time
from typing import Iterator
import requests

from frequencyman.static_lang_data import DEFAULT_WF_LISTS_SOURCES
from frequencyman.text_processing import LangId
from frequencyman.language_data import WordFrequencyLists


def add_en_contractions(wf_list: list[str]) -> None:

    contractions = {
        "don't": ("do", "not"),
        "i'll": ("i", "will"),
        "didn't": ("did", "not"),
        "can't": ("can", "not"),
        "you're": ("you", "are"),
        "i've": ("i", "have"),
        "we're": ("we", "are"),
        "doesn't": ("does", "not"),
        "won't": ("will", "not"),
        "we'll": ("we", "will"),
        "they're": ("they", "are"),
        "you'll": ("you", "will"),
        "haven't": ("have", "not"),
        "couldn't": ("could", "not"),
        "wouldn't": ("would", "not"),
        "isn't": ("is", "not"),
        "you've": ("you", "have"),
        "aren't": ("are", "not"),
        "shouldn't": ("should", "not"),
        "we've": ("we", "have"),
        "you'd": ("you", "would"),
        "weren't": ("were", "not"),
        "hasn't": ("has", "not"),
        "wasn't": ("was", "not"),
        "they'll": ("they", "will"),
        "we'd": ("we", "would"),
        "hadn't": ("had", "not"),
        "they've": ("they", "have"),
        "she'll": ("she", "will"),
        "would've": ("would", "have"),
        "he'll": ("he", "will"),
        "must've": ("must", "have"),
        "should've": ("should", "have"),
        "that'll": ("that", "will"),
        "they'd": ("they", "would"),
        "could've": ("could", "have"),
        "cannot": ("can", "not")
    }

    # For each contraction, find the position to insert it
    for contraction, (word1, word2) in contractions.items():

        assert contraction == contraction.lower()
        assert word1 == word1.lower()
        assert word2 == word2.lower()

        if contraction in wf_list:
            continue

        # Find positions of both words
        if word1 == 'i':
            pos1 = 0
        else:
            pos1 = wf_list.index(word1)

        pos2 = wf_list.index(word2)

        # Calculate the difference between positions
        space = int((abs(pos2 - pos1) + 125) * 5)

        # Use the maximum position plus the difference as the target position
        target_position = max(pos1, pos2) + space

        # Ensure we don't exceed list length
        target_position = min(target_position, len(wf_list))

        wf_list.insert(target_position, contraction)


def get_words_from_content(response: requests.Response, lang_id: LangId, wf_list_url: str) ->  Iterator[str]:

    content: Iterator[str] = (line for line in response.iter_lines(decode_unicode=True) if line and line[0] != "'")

    for word, _ in WordFrequencyLists.get_words_from_content(content, wf_list_url, lang_id):

        if word[0] in {'-'}:
            continue

        word = word.strip("!@#$%^&*()_-=+{}:\"<>?,./;' ")

        if str(lang_id) in {"en", "fr", "it", "de", "es", "el"}:
            word = word.replace("’", "'")
            word = word.replace("`", "'")

        if word:
            yield word



WF_LIST_LENGTH_LIMIT = 15_000
WF_LIST_FILE_SIZE_LIMIT = 100_000
WF_LIST_TARGET_DIR = 'default_wf_lists'

def download_default_wf_lists():

    for lang_id, wf_list_url in DEFAULT_WF_LISTS_SOURCES.items():

            print("{} => {}".format(lang_id, wf_list_url))
            target_file = os.path.join(WF_LIST_TARGET_DIR, lang_id+'.txt')

            if os.path.isfile(target_file):
                print(format("File {} already exists!".format(target_file)))
                continue

            response = requests.get(wf_list_url, stream=True)
            response.raise_for_status()

            wf_list: list[str] = []
            words_added: set[str] = set()
            wf_list_size = 0

            for word in get_words_from_content(response, LangId(lang_id[:2]), wf_list_url):

                if word in words_added:
                    continue

                wf_list.append(word)
                wf_list_size += len(word.encode("utf-8"))
                words_added.add(word)

                if len(wf_list) > WF_LIST_LENGTH_LIMIT:
                    break
                if wf_list_size > WF_LIST_FILE_SIZE_LIMIT:
                    break

            if wf_list:
                if lang_id == 'en':
                    add_en_contractions(wf_list)
                    wf_list = wf_list[:WF_LIST_LENGTH_LIMIT]
                # Write the list to a file
                with open(target_file, "w", encoding="utf-8") as f:
                    wf_list_content = "\n".join(wf_list)
                    f.write(wf_list_content)

            time.sleep(1)


if __name__ == "__main__":
    download_default_wf_lists()
    print("Done!")







