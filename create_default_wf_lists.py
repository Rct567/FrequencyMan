import os
import time
import requests

from frequencyman.static_lang_data import DEFAULT_WF_LISTS_SOURCES
from frequencyman.text_processing import LangId
from frequencyman.language_data import WordFrequencyLists


def add_en_contractions(wf_list: list[str]) -> list[str]:
    # Dictionary of contractions from previous artifact
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

    # Create a new list to store results
    result = wf_list.copy()

    # For each contraction, find the position to insert it
    for contraction, (word1, word2) in contractions.items():

        # Find positions of both words
        if word1 == 'i':
            pos1 = 0
        else:
            pos1 = wf_list.index(word1.lower())

        pos2 = wf_list.index(word2.lower())

        # Calculate the difference between positions
        space = int((abs(pos2 - pos1) + 125) * 5)

        # Use the maximum position plus the difference as the target position
        target_position = max(pos1, pos2) + space

        # Ensure we don't exceed list length
        target_position = min(target_position, len(result))

        # Add the contraction if it's not already in the list
        if contraction.lower() in result:
            raise Exception("Contraction {} already in list!".format(contraction))

        result.insert(target_position, contraction.lower())


    return result

def download_default_wf_lists():

    target_dir = 'default_wf_lists'

    for lang_id, wf_list_url in DEFAULT_WF_LISTS_SOURCES.items():

            print(wf_list_url)
            target_file = os.path.join(target_dir, lang_id+'.txt')

            if os.path.isfile(target_file):
                continue

            response = requests.get(wf_list_url)

            if response.status_code // 100 != 2:
                raise Exception("Error downloading file \"{}\". Status code: {}".format(wf_list_url, response.status_code))

            temp_file = os.path.join(target_dir, os.path.basename(wf_list_url))

            with open(temp_file, 'wb') as f:
                f.write(response.content)

            wf_list: list[str] = []
            wf_list_size = 0
            for word, _ in WordFrequencyLists.get_words_from_file(temp_file, LangId(lang_id[:2])):

                wf_list.append(word)
                wf_list_size += len(word.encode("utf-8"))

                if len(wf_list) > 50_000:
                    break
                if wf_list_size > 80_000:
                    break

            if wf_list:
                if lang_id == 'en':
                    wf_list = add_en_contractions(wf_list)
                with open(target_file, "w", encoding="utf-8") as f:
                    wf_list_content = "\n".join(wf_list)
                    f.write(wf_list_content)

            os.remove(temp_file)
            time.sleep(1)


if __name__ == "__main__":
    download_default_wf_lists()
    print("Done!")







