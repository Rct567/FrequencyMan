import os
import time
from typing import Iterable, Iterator
import requests

from frequencyman.static_lang_data import LANGUAGE_NAMES_ENG_AND_NATIVE, get_default_wf_list_sources
from frequencyman.text_processing import LangId, TextProcessing
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


def get_words_from_content(response: requests.Response, lang_id: LangId, wf_list_url: str) -> Iterator[str]:

    content: Iterator[str] = (line.decode('utf-8') for line in response.iter_lines())
    content_filters = (line for line in content if line and line[0] != "'" and line[0] != '-' and ("--" not in line[0]))

    for word, _ in WordFrequencyLists.get_words_from_content(content_filters, wf_list_url, lang_id):

        word = word.strip("!@#$%^&*()_-=+{}:\"<>?,./;' ")

        if str(lang_id) in {'en', 'fr', 'it', 'ga', 'pt', 'de', 'nl', 'sv', 'fi', 'mt', 'ca', 'oc'}:
            word = word.replace("’", "'")
            word = word.replace("`", "'")

        if str(lang_id) in {'en', 'nl', 'af'}:
            if word[-1] == "s" and word[-2] == "'":
                word = word[:-2]

        if (str(lang_id) in {'vi', 'sr', 'th'}):
            if " " in word:
                word = word.split(" ")[0]
            if not TextProcessing.get_word_accepter(lang_id)(word):
                word = ""

        assert not " " in word

        if word:
            yield word


SOURCE_WF_LIST_LENGTH_LIMIT = 1_000_000
LANG_REQUIRED_WF_LIST_LENGTH = 4_000
RESULT_WF_LIST_LENGTH_LIMIT = 15_000
RESULT_WF_LIST_FILE_SIZE_LIMIT = 120_000
RESULT_WF_LIST_DIR = 'default_wf_lists'


def create_default_wf_lists():

    for lang_id, wf_list_urls in get_default_wf_list_sources().items():

        result_wf_file = os.path.join(RESULT_WF_LIST_DIR, lang_id+'.txt')

        print("Creating WF LIST for {}".format(LANGUAGE_NAMES_ENG_AND_NATIVE[lang_id]['name']))

        if os.path.isfile(result_wf_file):
            print(format(" File {} already exists!".format(result_wf_file)))
            continue

        print(" Downloading {} files...".format(len(wf_list_urls)))

        wf_lists: list[list[str]] = []

        for wf_list_url in wf_list_urls:

            print(" {} => {}".format(lang_id, wf_list_url))

            response = requests.get(wf_list_url, stream=True)
            response.raise_for_status()

            wf_list: list[str] = []
            words_added: set[str] = set()

            for word in get_words_from_content(response, LangId(lang_id[:2]), wf_list_url):

                if word in words_added:
                    continue

                wf_list.append(word)
                words_added.add(word)

                if len(wf_list) > SOURCE_WF_LIST_LENGTH_LIMIT:
                    break

            if len(wf_list) < 100:
                print(" WARNING: WF list not used! {} contains only {} words!".format(wf_list_url, len(wf_list)))
            else:
                wf_lists.append(wf_list)


        lang_has_long_wf_list = any(len(wf_list) > LANG_REQUIRED_WF_LIST_LENGTH for wf_list in wf_lists)

        if not lang_has_long_wf_list:
            print(" WARNING: No long WF list found for {}!".format(lang_id))
            print(" No combined WF list created...")
            continue

        if lang_id == 'en':
            for wf_list in wf_lists:
                add_en_contractions(wf_list)

        combined = ((((word, position+1) for position, word in enumerate(wf_list))) for wf_list in wf_lists)
        result_wf_list = []
        wf_list_size = 0

        for word in WordFrequencyLists.combine_lists_by_avg_position(combined):

            result_wf_list.append(word)
            wf_list_size += len(word.encode("utf-8"))

            if len(result_wf_list) > RESULT_WF_LIST_LENGTH_LIMIT:
                break
            if wf_list_size > RESULT_WF_LIST_FILE_SIZE_LIMIT:
                break

        if not result_wf_list:
            raise Exception("Resulting word frequency list is empty!")

        result_wf_list = result_wf_list[:RESULT_WF_LIST_LENGTH_LIMIT]

        # Write the list to a file

        with open(result_wf_file, "w", encoding="utf-8") as f:
            wf_list_content = "\n".join(result_wf_list)
            f.write(wf_list_content)
            print(" Combined WF list {} created with {} words.".format(result_wf_file, len(result_wf_list)))

        time.sleep(1)

def create_ignore_candidates_list():

    print("Creating ignore candidates list...")

    ignore_candidates_file = os.path.join(RESULT_WF_LIST_DIR, 'ignore_candidates.txt')

    if os.path.isfile(ignore_candidates_file):
        print(format(" File {} already exists!".format(ignore_candidates_file)))
        return

    all_words: dict[str, int] = {}

    for lang_id in get_default_wf_list_sources():

        if lang_id[:3] == 'ze_':
            continue

        wf_list_file = os.path.join(RESULT_WF_LIST_DIR, lang_id+'.txt')

        if not os.path.isfile(wf_list_file):
            continue

        for word, _ in WordFrequencyLists.get_words_from_file(wf_list_file, LangId(lang_id[:2])):

            if word in all_words:
                 if lang_id not in {'nl', 'da', "no"}:
                    all_words[word] += 1
            else:
                all_words[word] = 1

    num_languages = len(get_default_wf_list_sources().keys())
    global_words = {word: round(1 - count/num_languages, 2) for word, count in all_words.items() if count > num_languages*0.15}
    global_words = dict(sorted(global_words.items(), key=lambda x: x[1], reverse=True))

    if len(global_words) < 1000:
        print(" Warning: Only {} words found!".format(len(global_words)))

    with open(ignore_candidates_file, "w", encoding="utf-8") as f:
        for word, count in global_words.items():
            f.write("{} {}\n".format(word, count))

    print(" File {} created!".format(ignore_candidates_file))


if __name__ == "__main__":
    create_default_wf_lists()
    create_ignore_candidates_list()
    print("Done!")
