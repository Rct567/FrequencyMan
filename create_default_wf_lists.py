import os
import time
import requests

from frequencyman.static_lang_data import DEFAULT_WF_LISTS_SOURCES
from frequencyman.text_processing import LangId
from frequencyman.language_data import WordFrequencyLists

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
                with open(target_file, "w", encoding="utf-8") as f:
                    wf_list_content = "\n".join(wf_list)
                    f.write(wf_list_content)

            os.remove(temp_file)
            time.sleep(1)


if __name__ == "__main__":
    download_default_wf_lists()
    print("Done!")







