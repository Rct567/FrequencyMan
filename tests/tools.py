import inspect
import os
import shutil
from typing import Callable, Optional, Sequence, Tuple

from frequencyman.language_data import LangDataId, LanguageData

from anki.collection import Collection, OpChanges, OpChangesWithCount

from anki.cards import CardId, Card
from anki.notes import Note, NoteId

from frequencyman.lib.cacher import Cacher
from frequencyman.lib.utilities import var_dump_log


def store_card_id_list(filename: str, int_list: Sequence[CardId]) -> None:
    with open(filename, 'w') as file:
        file.write('\n'.join(map(str, int_list)))

def read_card_id_list(filename: str) -> Sequence[CardId]:
    with open(filename, 'r') as file:
        int_list = [CardId(int(line.strip())) for line in file]
    return int_list

class TestCollections:

    TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
    TEST_COLLECTIONS_DIR = os.path.join(TEST_DATA_DIR, 'collections')
    CACHER_FILE_PATH = os.path.join(TEST_DATA_DIR, 'cacher_data.sqlite')
    CACHER: Optional[Cacher] = None
    cacher_data_cleared = False

    @staticmethod
    def get_test_collection(test_collection_name: str) -> Tuple[Collection, LanguageData, Cacher, Callable[[Sequence[CardId]], None]]:

        caller_frame = inspect.stack()[1]
        caller_fn_name = caller_frame.function
        assert caller_fn_name.startswith('test_')
        caller_class_name = caller_frame.frame.f_locals['self'].__class__.__name__
        assert caller_class_name.startswith('Test')
        caller_full_name = "{}_{}".format(caller_class_name[4:], caller_fn_name[5:])

        collection_dir = os.path.join(TestCollections.TEST_COLLECTIONS_DIR, test_collection_name)
        lang_data_dir = os.path.join(collection_dir, 'lang_data')

        lang_data = LanguageData(lang_data_dir)

        # cacher
        if TestCollections.CACHER is None:
            if not TestCollections.cacher_data_cleared and os.path.exists(TestCollections.CACHER_FILE_PATH):
                os.remove(TestCollections.CACHER_FILE_PATH)
                TestCollections.cacher_data_cleared = True
            TestCollections.CACHER = Cacher(TestCollections.CACHER_FILE_PATH)
        else:
            TestCollections.CACHER.close()

        # create temporary collection
        collection_src_path = os.path.join(collection_dir, test_collection_name+".anki2")
        temp_collection_file_name = test_collection_name+"_"+str(caller_full_name)+"_temp.anki2"
        temp_collection_path = os.path.join(collection_dir, temp_collection_file_name)
        if os.path.exists(temp_collection_path):
            os.remove(temp_collection_path)
        shutil.copy(collection_src_path, temp_collection_path)

        # helper function used to lock-in and assert order
        def assert_locked_order(sorted_cards_ids: Sequence[CardId]):
            order_file_path = os.path.join(collection_dir, 'expected_order_{}.txt'.format(caller_full_name))

            if os.path.exists(order_file_path):
                expected_order = read_card_id_list(order_file_path)
                assert sorted_cards_ids == expected_order, "Order file '{}' for '{}' didn't match!".format(order_file_path, test_collection_name)
            else:
                store_card_id_list(order_file_path, sorted_cards_ids)
                print("WARNING: Order file '{}' for '{}' didn't exist yet!".format(order_file_path, test_collection_name))

        # return result
        return Collection(temp_collection_path), lang_data, TestCollections.CACHER, assert_locked_order
