from ast import TypeAlias
import inspect
import os
import shutil
from typing import Any, AnyStr, Callable, Generator, Optional, Sequence, Tuple, TypeVar, override

from anki.collection import Collection

from anki.cards import CardId, Card
from anki.notes import Note, NoteId

from frequencyman.language_data import LangDataId, LanguageData
from frequencyman.lib.cacher import Cacher
from frequencyman.lib.utilities import var_dump_log

class TestCollection(Collection):
    collection_name: str
    collection_dir: str
    lang_data: LanguageData
    cacher: Cacher

    caller_class_name: str
    caller_full_name: str

    def __init__(self, collection_name: str, collection_dir: str, lang_data: LanguageData, caller_frame: inspect.FrameInfo):
        self.collection_name = collection_name
        self.collection_dir = collection_dir
        self.caller = caller_frame
        self.lang_data = lang_data

        caller_fn_name = caller_frame.function
        assert caller_fn_name.startswith('test_')
        self.caller_class_name = caller_frame.frame.f_locals['self'].__class__.__name__
        assert self.caller_class_name.startswith('Test')
        self.caller_full_name = "{}_{}".format(self.caller_class_name, caller_fn_name)

        # cacher
        if TestCollections.CACHER is None:
            if not TestCollections.cacher_data_cleared and os.path.exists(TestCollections.CACHER_FILE_PATH):
                os.remove(TestCollections.CACHER_FILE_PATH)
                TestCollections.cacher_data_cleared = True
            TestCollections.CACHER = Cacher(TestCollections.CACHER_FILE_PATH)
        else:
            TestCollections.CACHER.close()
        self.cacher = TestCollections.CACHER

        # create temporary collection
        collection_src_path = os.path.join(collection_dir, collection_name+".anki2")
        temp_collection_file_name = collection_name+"_"+str(self.caller_full_name)+"_temp.anki2"
        temp_collection_path = os.path.join(collection_dir, temp_collection_file_name)
        if os.path.exists(temp_collection_path):
            os.remove(temp_collection_path)
        shutil.copy(collection_src_path, temp_collection_path)

        # init anki collection
        super().__init__(temp_collection_path)

    def __get_lock_file_path(self, lock_name: str, lock_dir: str) -> str:
        assert lock_name != ''
        order_file_dir = os.path.join(self.collection_dir, lock_dir)
        if not os.path.exists(order_file_dir):
            os.makedirs(order_file_dir)
        return os.path.join(order_file_dir, '{}_{}.txt'.format(self.caller_full_name, lock_name))

    # helper function used to lock-in and assert result
    def lock_and_assert_result(self, lock_name: str,  result_data: Any):
        result_file_path = self.__get_lock_file_path(lock_name, 'locked_results')

        if os.path.exists(result_file_path):
            with open(result_file_path, 'r') as file:
                expected_result = file.read()
            assert str(result_data) == expected_result, "Result file '{}' for '{}' didn't match!".format(result_file_path, self.collection_name)
        else:
            with open(result_file_path, 'w') as file:
                file.write(str(result_data))
            print("WARNING: Result file '{}' for '{}' didn't exist yet!".format(result_file_path, self.collection_name))


    # helper function used to lock-in and assert order
    def lock_and_assert_order(self, lock_name: str, sorted_items: Sequence[Any]):

        order_file_path = self.__get_lock_file_path(lock_name, 'locked_orders')

        if os.path.exists(order_file_path):
            with open(order_file_path, 'r') as file:
                expected_order = [line.rstrip() for line in file]
            for i, line in enumerate(expected_order):
                assert line == str(sorted_items[i]), "Order file '{}' for '{}' didn't match on line {}!".format(order_file_path, self.collection_name, i)
        else:
            with open(order_file_path, 'w') as file:
                file.write('\n'.join(map(str, sorted_items)))
            print("WARNING: Order file '{}' for '{}' didn't exist yet!".format(order_file_path, self.collection_name))


class TestCollections:

    TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
    TEST_COLLECTIONS_DIR = os.path.join(TEST_DATA_DIR, 'collections')
    CACHER_FILE_PATH = os.path.join(TEST_DATA_DIR, 'cacher_data.sqlite')
    CACHER: Optional[Cacher] = None
    cacher_data_cleared = False

    @staticmethod
    def get_test_collection(test_collection_name: str) -> TestCollection:

        collection_dir = os.path.join(TestCollections.TEST_COLLECTIONS_DIR, test_collection_name)
        lang_data_dir = os.path.join(collection_dir, 'lang_data')

        lang_data = LanguageData(lang_data_dir)
        caller_frame = inspect.stack()[1]

        return TestCollection(test_collection_name, collection_dir, lang_data, caller_frame)
