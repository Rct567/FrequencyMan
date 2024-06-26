import os
import re
from typing import Generator
import pytest

from frequencyman.target_list import TargetList, TargetListReorderResult
from frequencyman.lib.event_logger import EventLogger

from frequencyman.target_reorder_logger import TargetReorderLogger
from tests.tools import TestCollections

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


@pytest.fixture
def reorder_logger(tmpdir: str) -> Generator[TargetReorderLogger, None, None]:
    db_path = os.path.join(tmpdir, 'test_reorder_log.sqlite')
    # db_path = os.path.join(TEST_DATA_DIR, 'test_reorder_log.sqlite')
    if os.path.exists(db_path):
        os.remove(db_path)
    reorder_logger = TargetReorderLogger(db_path)
    yield reorder_logger
    reorder_logger.close()

class TestTargetReorderLogger:

    def test_reorder_logger(self, reorder_logger: TargetReorderLogger) -> None:

        col = TestCollections.get_test_collection('two_deck_collection')

        target_list = TargetList(col.lang_data, col.cacher, col)

        target_list.set_targets([
            {
                'id': 'target1',
                'decks': 'decka',
                'notes': [{
                    "name": "Basic",
                    "fields": {
                        "Front": "EN",
                        "Back": "ES"
                    },
                }]
            },
            {
                'id': 'target2',
                'decks': 'deckb',
                'notes': [{
                    "name": "Basic",
                    "fields": {
                        "Front": "EN",
                        "Back": "ES"
                    },
                }]
            }
        ])

        event_logger = EventLogger()
        result = target_list.reorder_cards(col, event_logger)

        reorder_logger.log_reordering(target_list, result)

        assert reorder_logger.count_rows("reorders") == 1
        assert reorder_logger.count_rows("targets") == 2
        assert reorder_logger.count_rows("target_segments") == 4
        assert reorder_logger.count_rows("target_languages") == 4