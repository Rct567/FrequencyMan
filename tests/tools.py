import os
import shutil
from typing import Final

from frequencyman.language_data import LangDataId, LanguageData

from anki.collection import Collection, OpChanges, OpChangesWithCount

from anki.cards import CardId, Card
from anki.notes import Note, NoteId

from frequencyman.lib.utilities import var_dump_log


def store_card_id_list(filename: str, int_list: list[CardId]) -> None:
    with open(filename, 'w') as file:
        file.write('\n'.join(map(str, int_list)))

def read_card_id_list(filename: str) -> list[CardId]:
    with open(filename, 'r') as file:
        int_list = [CardId(int(line.strip())) for line in file]
    return int_list


all_tests_collection_seq_num: Final[dict[str, int]] = {}

class TestCollections:

    TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
    TEST_COLLECTIONS_DIR = os.path.join(TEST_DATA_DIR, 'collections')

    def __init__(self):

        assert 'test_collection_seq_num' in globals()
        assert isinstance(all_tests_collection_seq_num, dict)

    @staticmethod
    def get_test_collection(test_collection_name: str):

        global all_tests_collection_seq_num

        if not test_collection_name in all_tests_collection_seq_num:
            all_tests_collection_seq_num[test_collection_name] = -1

        all_tests_collection_seq_num[test_collection_name] += 1
        assert all_tests_collection_seq_num[test_collection_name] >= 0
        collection_seq_num: Final[int] = all_tests_collection_seq_num[test_collection_name]

        collection_dir = os.path.join(TestCollections.TEST_COLLECTIONS_DIR, test_collection_name)
        lang_data_dir = os.path.join(collection_dir, 'lang_data')

        lang_data = LanguageData(lang_data_dir)

        # create temporary collection
        collection_src_path = os.path.join(collection_dir, test_collection_name+".anki2")
        temp_collection_file_name = test_collection_name+"_"+str(collection_seq_num)+"_temp.anki2"
        temp_collection_path = os.path.join(collection_dir, temp_collection_file_name)
        if os.path.exists(temp_collection_path):
            os.remove(temp_collection_path)
        shutil.copy(collection_src_path, temp_collection_path)

        # helper function used to lock-in and assert order
        def assert_locked_order(sorted_cards_ids: list[CardId]):
            order_file = os.path.join(collection_dir, 'expected_order_{}.txt'.format(collection_seq_num))

            if os.path.exists(order_file):
                expected_order = read_card_id_list(order_file)
                assert sorted_cards_ids == expected_order, "Order file {} for '{}' didn't match!".format(order_file, test_collection_name)
            else:
                store_card_id_list(order_file, sorted_cards_ids)
                print("WARNING: Order file for '{}' didn't exist yet!".format(test_collection_name))

        # return result
        return Collection(temp_collection_path), lang_data, assert_locked_order
