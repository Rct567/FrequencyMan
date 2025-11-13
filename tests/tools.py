from contextlib import contextmanager
import inspect
import os
from pathlib import Path
import shutil
from typing import Any, Generator, Optional, Sequence
import pprint
import time
from dateutil.parser import parse

from anki.collection import Collection

from frequencyman.language_data import LanguageData
from frequencyman.lib.persistent_cacher import PersistentCacher, SqlDbFile
from frequencyman.lib.utilities import var_dump_log


class TestCollection(Collection):
    collection_name: str
    collection_dir: str
    lang_data: LanguageData
    cacher: PersistentCacher

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
            TestCollections.CACHER = PersistentCacher(SqlDbFile(TestCollections.CACHER_FILE_PATH))
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
        result_data_str = pprint.pformat(result_data, width=10000)

        if os.path.exists(result_file_path):
            with open(result_file_path, 'r', encoding="utf-8") as file:
                expected_result = file.read().splitlines()
            result_lines = result_data_str.splitlines()
            assert len(expected_result) == len(result_lines)
            for line_num, (expected_line, result_line) in enumerate(zip(expected_result, result_lines)):
                assert expected_line.strip() == result_line.strip(), (
                    "Result file '{}' for '{}' didn't match at line {}!\nDiff:\n\"{}\"\nnot equal expected:\n\"{}\""
                    .format(result_file_path, self.collection_name, line_num, result_line, expected_line)
                )
        else:
            with open(result_file_path, 'w', encoding="utf-8") as file:
                file.write(result_data_str)
            print("WARNING: Result file '{}' for '{}' didn't exist yet!".format(result_file_path, self.collection_name))

    # helper function used to lock-in and assert order

    def lock_and_assert_order(self, lock_name: str, sorted_items: Sequence[Any]):

        order_file_path = self.__get_lock_file_path(lock_name, 'locked_orders')

        if os.path.exists(order_file_path):
            with open(order_file_path, 'r', encoding="utf-8") as file:
                expected_order = [line.rstrip() for line in file]
            for line_num, expected_line in enumerate(expected_order):
                result_item = str(sorted_items[line_num]).rstrip()
                assert expected_line == result_item, (
                    "Order file '{}' for '{}' didn't match on line {}!\nDiff:\n\"{}\"\nnot equal expected:\n\"{}\""
                    .format(order_file_path, self.collection_name, line_num, result_item, expected_line)
                )
        else:
            with open(order_file_path, 'w', encoding="utf-8") as file:
                file.write('\n'.join(map(str, sorted_items)))
            print("WARNING: Order file '{}' for '{}' didn't exist yet!".format(order_file_path, self.collection_name))


class TestCollections:

    TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
    TEST_COLLECTIONS_DIR = os.path.join(TEST_DATA_DIR, 'collections')
    CACHER_FILE_PATH = os.path.join(TEST_DATA_DIR, 'cacher_data.sqlite')
    CACHER: Optional[PersistentCacher] = None
    cacher_data_cleared = False

    @staticmethod
    def run_cleanup_routine():

        if os.path.exists(TestCollections.CACHER_FILE_PATH):
            try:
                os.remove(TestCollections.CACHER_FILE_PATH)
            except OSError:
                pass

        test_collection_folder = Path(TestCollections.TEST_COLLECTIONS_DIR)
        for file in test_collection_folder.rglob("*_temp.anki2"):
            try:
                file.unlink(missing_ok=True)
            except OSError:
                pass
        for file in test_collection_folder.rglob("*_temp.anki2-wal"):
            try:
                file.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def get_test_collection(test_collection_name: str) -> TestCollection:

        TestCollections.run_cleanup_routine()

        collection_dir = os.path.join(TestCollections.TEST_COLLECTIONS_DIR, test_collection_name)
        lang_data_dir = os.path.join(collection_dir, 'lang_data')

        lang_data = LanguageData(lang_data_dir)
        caller_frame = inspect.stack()[1]

        return TestCollection(test_collection_name, collection_dir, lang_data, caller_frame)


@contextmanager
def freeze_time_anki(target_time_str: str) -> Generator[None, None, None]:
    """
    A context manager to mock time.time() to return a specific target time based on a string input.

    :param target_time_str: The target time as a string (e.g., "2023-12-05" or "2023-12-05 13:00").
    :yield: None
    """
    target_datetime = parse(target_time_str)
    target_timestamp = target_datetime.timestamp()

    original_time = time.time
    time.time = lambda: target_timestamp
    try:
        yield
    finally:
        time.time = original_time
