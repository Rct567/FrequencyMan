import pytest
import os
from typing import Any, Generator
from frequencyman.lib.persistent_cacher import PersistentCacher

# Utility function for producing a dummy value


def dummy_producer() -> str:
    return "dummy_value"


@pytest.fixture
def cacher(tmpdir: str) -> Generator[PersistentCacher, None, None]:
    db_path = os.path.join(tmpdir, "test_cache.db")
    cacher = PersistentCacher(db_path, save_buffer_limit=2)
    yield cacher
    cacher.close()


def test_save_and_get_item(cacher: PersistentCacher) -> None:
    cacher.save_item("test_key", "test_value")
    assert cacher.get_item("test_key", dummy_producer) == "test_value"


def test_get_item_with_producer(cacher: PersistentCacher) -> None:
    assert cacher.get_item("new_key", dummy_producer) == "dummy_value"
    assert cacher.get_item("new_key", lambda: 'not_dummy') == "dummy_value"


def test_delete_item(cacher: PersistentCacher) -> None:
    cacher.delete_item("delete_key")
    assert cacher.num_items_stored() == 0
    # save two
    assert cacher.get_item("delete_key", producer=lambda: 'to_be_deleted') == "to_be_deleted"
    cacher.save_item("delete_key_2", "to_be_deleted")
    cacher.flush_save_buffer()
    assert cacher.num_items_stored() == 2
    # delete one
    cacher.delete_item("delete_key")
    assert cacher.num_items_stored() == 1
    # delete other one
    cacher.delete_item("delete_key_2")
    assert cacher.num_items_stored() == 0
    # add back
    assert cacher.get_item("delete_key", dummy_producer) == "dummy_value"
    assert cacher.get_item("delete_key_2", dummy_producer) == "dummy_value"
    cacher.flush_save_buffer()
    assert cacher.num_items_stored() == 2


def test_flush_save_buffer_on_close(cacher: PersistentCacher) -> None:
    assert cacher.get_item("new_key", dummy_producer) == "dummy_value"
    cacher.close()
    assert cacher.num_items_stored() == 1
    assert cacher.get_item("new_key", lambda: 'not_dummy') == "dummy_value"


def test_pre_load_all_items(cacher: PersistentCacher) -> None:
    cacher.save_item("preload_key", "preloaded_value")
    cacher.flush_save_buffer()  # Make sure data is saved to DB
    cacher.pre_load_all_items()
    assert cacher.get_item("preload_key", dummy_producer) == "preloaded_value"
    cacher.delete_item("preload_key")
    assert cacher.get_item("preload_key", dummy_producer) == "dummy_value"


def test_item_str_list(cacher: PersistentCacher) -> None:
    assert cacher.get_item("str_list_key", lambda: ["a", "b", "c"]) == ["a", "b", "c"]
    cacher.clear_pre_loaded_cache()
    cacher.flush_save_buffer()
    assert cacher.get_item("str_list_key", dummy_producer) == ["a", "b", "c"]


def test_item_str(cacher: PersistentCacher) -> None:
    assert cacher.get_item("str_key", lambda: "a") == "a"
    cacher.clear_pre_loaded_cache()
    cacher.flush_save_buffer()
    assert cacher.get_item("str_key", dummy_producer) == "a"


def test_item_dict(cacher: PersistentCacher) -> None:
    assert cacher.get_item("dict_key", lambda: {"a": 1, "b": 2, "c": []}) == {"a": 1, "b": 2, "c": []}
    cacher.clear_pre_loaded_cache()
    cacher.flush_save_buffer()
    assert cacher.get_item("dict_key", dummy_producer) == {"a": 1, "b": 2, "c": []}


def test_item_list(cacher: PersistentCacher) -> None:
    assert cacher.get_item("list_key", lambda: [1, 2, 3, 4]) == [1, 2, 3, 4]
    cacher.clear_pre_loaded_cache()
    cacher.flush_save_buffer()
    assert cacher.get_item("list_key", dummy_producer) == [1, 2, 3, 4]


def test_item_empty_list(cacher: PersistentCacher) -> None:
    assert cacher.get_item("empty_list_key", lambda: []) == []
    assert cacher.get_item("empty_list_str_key", lambda: ['']) == ['']
    cacher.clear_pre_loaded_cache()
    cacher.flush_save_buffer()
    assert cacher.get_item("empty_list_key", dummy_producer) == []
    assert cacher.get_item("empty_list_str_key", dummy_producer) == ['']


def test_different_items(cacher: PersistentCacher) -> None:

    items: list[Any] = [
        None,
        True,
        False,
        0,
        1,
        -1,
        1.0,
        -1.0,
        "a",
        "b",
        "c",
        [],
        [''],
        [{}, {}, {}],
        [1, 2, 3, 4],
        ["1", "2", "3", ""],
        {'a': 1, 'b': 2, 'c': []},
        "TEST"
    ]

    cacher.clear_pre_loaded_cache()
    cacher.flush_save_buffer()

    for index, item in enumerate(items):

        key = "item_{}".format(index)
        cacher.delete_item(key)
        cacher.save_item(key, item)
        # get from db
        cacher.clear_pre_loaded_cache()
        cacher.flush_save_buffer()
        assert cacher.get_item(key, dummy_producer) == item
        # test deleting
        cacher.delete_item(key)
        assert cacher.get_item(key, dummy_producer) == "dummy_value"
