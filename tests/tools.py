from __future__ import annotations

from contextlib import contextmanager
import inspect
from itertools import chain
import os
from pathlib import Path
import shutil
from typing import Any, Optional, NamedTuple, Callable, TypeVar, TYPE_CHECKING
from collections.abc import Generator, Sequence
if TYPE_CHECKING:
    from typing_extensions import TypeAlias
import pprint
import time
from dateutil.parser import parse
import atexit
import pytest

from anki.collection import Collection
from anki.media import media_paths_from_col_path

from frequencyman.language_data import LanguageData
from frequencyman.lib.persistent_cacher import PersistentCacher, SqlDbFile


CURRENT_PID = os.getpid()


T = TypeVar('T', bound=Callable[..., Any])


def with_test_collection(name: str) -> Callable[[T], T]:
    """
    Decorator that attaches the collection name to the test function object.
    The 'test_collection' fixture will read that attribute from request.function.
    """
    def decorator(func: T) -> T:
        setattr(func, "_test_collection_name", name)
        return func
    return decorator



@pytest.fixture
def test_collection(request: pytest.FixtureRequest) -> Generator[MockCollection, None, None]:
    """
    Fixture that yields the collection named by @with_test_collection(...).
    Raises a RuntimeError if the decorator was not applied.
    """

    name: Optional[str] = getattr(request.function, "_test_collection_name", None)
    if name is None:
        raise RuntimeError(
            "test_collection fixture used but no @with_test_collection(...) decorator found."
        )

    caller_context = CallerContext(
        test_instance=request.instance,
        test_function_name=request.function.__name__
    )

    col = MockCollections.get_test_collection(name, caller_context)

    try:
        yield col
    finally:
        col.remove()  # remove test collection after test


class CallerContext(NamedTuple):
    caller_frame: Optional[inspect.FrameInfo] = None
    test_instance: Optional[object] = None
    test_function_name: Optional[str] = None


class MockCollection(Collection):
    collection_name: str
    collection_dir: Path
    lang_data: LanguageData
    cacher: PersistentCacher

    caller_class_name: str
    caller_full_name: str

    @staticmethod
    def _find_test_caller_info(context: CallerContext) -> tuple[str, str]:
        """
        Find the test caller information (function name and class name).

        Tries multiple strategies in order:
        1. Explicitly provided in context (test_instance, test_function_name) - for fixtures
        2. Provided caller_frame - for backward compatibility (e.g. get_test_collection)
        3. Stack inspection - for direct calls from test methods

        Returns: (caller_class_name, caller_fn_name)
        Raises: RuntimeError if test caller cannot be determined
        """
        # Strategy 1: Explicitly provided in context (highest priority)
        if context.test_instance is not None and context.test_function_name is not None:
            if context.test_function_name.startswith('test_') and context.test_instance.__class__.__name__.startswith('Test'):
                return (context.test_instance.__class__.__name__, context.test_function_name)

        # Strategy 2: Provided frame (backward compatibility)
        if context.caller_frame is not None:
            if (context.caller_frame.function.startswith('test_') and
                'self' in context.caller_frame.frame.f_locals and
                context.caller_frame.frame.f_locals['self'].__class__.__name__.startswith('Test')):
                return (context.caller_frame.frame.f_locals['self'].__class__.__name__, context.caller_frame.function)

        # Strategy 3: Stack inspection (fallback)
        for frame_info in inspect.stack():
            if (frame_info.function.startswith('test_') and
                'self' in frame_info.frame.f_locals):
                self_obj = frame_info.frame.f_locals['self']
                if self_obj.__class__.__name__.startswith('Test'):
                    return (self_obj.__class__.__name__, frame_info.function)

        # Failed to find test caller
        raise RuntimeError(
            "Could not find test method frame. MockCollection must be called from within a test method " +
            "(function starting with 'test_' in a class starting with 'Test'), or test_instance and " +
            "test_function_name must be provided."
        )

    def __init__(self, collection_name: str, collection_dir: Path, lang_data: LanguageData,
                 caller_context: Optional[CallerContext] = None):
        self.collection_name = collection_name
        self.collection_dir = collection_dir
        self.lang_data = lang_data

        # Find test caller information
        if caller_context is None:
            caller_context = CallerContext()

        self.caller_class_name, caller_fn_name = self._find_test_caller_info(caller_context)
        self.caller_full_name = f"{self.caller_class_name}_{caller_fn_name}"
        assert self.caller_class_name.startswith('Test')
        assert caller_fn_name.startswith('test_')

        # cacher
        MockCollections.clear_cacher()
        MockCollections.CACHER = PersistentCacher(SqlDbFile(MockCollections.CACHER_FILE_PATH))
        self.cacher = MockCollections.CACHER

        # create temporary collection
        collection_src_path = collection_dir / (collection_name+".anki2")
        temp_collection_file_name = "{}_{}_{}_temp.anki2".format(collection_name, self.caller_full_name, CURRENT_PID)
        temp_collection_path = collection_dir / temp_collection_file_name
        if temp_collection_path.exists():
            temp_collection_path.unlink()
        shutil.copy(collection_src_path, temp_collection_path)

        # init anki collection
        super().__init__(str(temp_collection_path))

    def __get_lock_file_path(self, lock_name: str, lock_dir: str) -> Path:
        assert lock_name != ''
        order_file_dir = self.collection_dir / lock_dir
        if not order_file_dir.exists():
            order_file_dir.mkdir(parents=True)
        return order_file_dir / '{}_{}.txt'.format(self.caller_full_name, lock_name)

    # helper function used to lock-in and assert result
    def lock_and_assert_result(self, lock_name: str,  result_data: Any):
        result_file_path = self.__get_lock_file_path(lock_name, 'locked_results')
        result_data_str = pprint.pformat(result_data, width=10000)

        if result_file_path.exists():
            with result_file_path.open('r', encoding="utf-8") as file:
                expected_result = file.read().splitlines()
            result_lines = result_data_str.splitlines()
            assert len(expected_result) == len(result_lines)
            for line_num, (expected_line, result_line) in enumerate(zip(expected_result, result_lines)):
                assert expected_line.strip() == result_line.strip(), (
                    "Result file '{}' for '{}' didn't match at line {}!\nDiff:\n\"{}\"\nnot equal expected:\n\"{}\""
                    .format(result_file_path, self.collection_name, line_num, result_line, expected_line)
                )
        else:
            with result_file_path.open('w', encoding="utf-8") as file:
                file.write(result_data_str)
            print("WARNING: Result file '{}' for '{}' didn't exist yet!".format(result_file_path, self.collection_name))

    # helper function used to lock-in and assert order

    def lock_and_assert_order(self, lock_name: str, sorted_items: Sequence[Any]):

        order_file_path = self.__get_lock_file_path(lock_name, 'locked_orders')

        if order_file_path.exists():
            with order_file_path.open('r', encoding="utf-8") as file:
                expected_order = [line.rstrip() for line in file]
            for line_num, expected_line in enumerate(expected_order):
                result_item = str(sorted_items[line_num]).rstrip()
                assert expected_line == result_item, (
                    "Order file '{}' for '{}' didn't match on line {}!\nDiff:\n\"{}\"\nnot equal expected:\n\"{}\""
                    .format(order_file_path, self.collection_name, line_num, result_item, expected_line)
                )
        else:
            with order_file_path.open('w', encoding="utf-8") as file:
                file.write('\n'.join(map(str, sorted_items)))
            print("WARNING: Order file '{}' for '{}' didn't exist yet!".format(order_file_path, self.collection_name))

    def remove(self):

        if self.db:
           self.close()

        MockCollections.clear_cacher()

        (media_dir, media_db) = media_paths_from_col_path(self.path)

        try:
            Path(media_db).unlink()
        except OSError:
            pass

        try:
            Path(media_dir).rmdir()
        except OSError:
            pass

        try:
            Path(self.path).unlink()
        except OSError:
            pass



MockCollectionFixture: TypeAlias = Callable[
    [pytest.FixtureRequest],
    Generator[MockCollection, None, None]
]

class MockCollections:

    TEST_DATA_DIR = Path(__file__).parent / 'data'
    TEST_COLLECTIONS_DIR = TEST_DATA_DIR / 'collections'
    CACHER_FILE_PATH = TEST_DATA_DIR / 'cacher_data_{}_temp.sqlite'.format(CURRENT_PID)
    CACHER: Optional[PersistentCacher] = None

    last_initiated_test_collection: Optional[MockCollection] = None

    @staticmethod
    def clear_cacher():
        if MockCollections.CACHER:
            MockCollections.CACHER.close()
            MockCollections.CACHER_FILE_PATH.unlink(missing_ok=True)
            MockCollections.CACHER = None

    @staticmethod
    def run_cleanup_routine():

        test_collection_folder = MockCollections.TEST_COLLECTIONS_DIR
        cutoff = time.time() - 30  # 30 seconds

        patterns = ["*_temp.anki2", "*_temp.anki2-wal", "*_temp.sqlite"]
        all_temp_files = chain.from_iterable(test_collection_folder.rglob(p) for p in patterns)

        try:
            for file in all_temp_files:
                name = file.name
                name_match  = name.endswith("_temp.anki2") or name.endswith("_temp.anki2-wal") or name.endswith("_temp.sqlite")
                if not name_match:
                    raise Exception("Invalid file name '{}'".format(name))
                try:
                    if file.stat().st_mtime < cutoff:
                        file.unlink(missing_ok=True)
                except OSError:
                    pass
        except FileNotFoundError as e:
            print("File '{}' got lost during cleanup routine. {}".format(e.filename, e.strerror))

        for path in test_collection_folder.glob("*/*"):
            if path.is_dir() and path.name.endswith("_temp.media"):
                try:
                    if path.stat().st_mtime < cutoff:
                        path.rmdir() # rmdir only succeeds if directory is empty
                except OSError:
                    pass # Not empty or cannot remove → ignore

    @staticmethod
    def get_test_collection(test_collection_name: str, caller_context: CallerContext) -> MockCollection:

        if MockCollections.last_initiated_test_collection:
            MockCollections.last_initiated_test_collection.remove()
        else: # set up cleanup routine on exit only once
            atexit.register(MockCollections.run_cleanup_routine)

        collection_dir = MockCollections.TEST_COLLECTIONS_DIR / test_collection_name
        lang_data_dir = collection_dir / 'lang_data'
        lang_data = LanguageData(lang_data_dir)

        # caller_frame = inspect.stack()[1]
        # caller_context = CallerContext(caller_frame=caller_frame)

        col = MockCollection(test_collection_name, collection_dir, lang_data, caller_context)

        MockCollections.last_initiated_test_collection = col
        atexit.register(col.remove)

        return col


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
