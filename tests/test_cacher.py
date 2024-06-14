import pytest
import os
import time
from typing import Generator
from frequencyman.lib.cacher import Cacher

# Utility function for producing a dummy value
def dummy_producer() -> str:
    return "dummy_value"

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


@pytest.fixture
def cacher(tmpdir: str) -> Generator[Cacher, None, None]:
    db_path = os.path.join(tmpdir, "test_cache.db")
    cacher = Cacher(db_path, save_buffer_limit=2)
    yield cacher
    cacher.close()

def test_save_and_get_item(cacher: Cacher) -> None:
    cacher.save_item("test_key", "test_value")
    assert cacher.get_item("test_key", dummy_producer) == "test_value"

def test_get_item_with_producer(cacher: Cacher) -> None:
    assert cacher.get_item("new_key", dummy_producer) == "dummy_value"
    assert cacher.get_item("new_key", lambda: 'not_dummy') == "dummy_value"

def test_delete_item(cacher: Cacher) -> None:
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

def test_pre_load_all_items(cacher: Cacher) -> None:
    cacher.save_item("preload_key", "preloaded_value")
    cacher.flush_save_buffer()  # Make sure data is saved to DB
    cacher.pre_load_all_items()
    assert cacher.get_item("preload_key", dummy_producer) == "preloaded_value"
