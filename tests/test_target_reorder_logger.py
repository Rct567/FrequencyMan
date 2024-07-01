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

        num_entries_added = reorder_logger.log_reordering(target_list, result)

        assert num_entries_added == 2
        assert reorder_logger.count_rows("reorders") == 1
        assert reorder_logger.count_rows("reordered_targets") == 2
        assert reorder_logger.count_rows("target_segments") == 4
        assert reorder_logger.count_rows("target_languages") == 4
        assert reorder_logger.count_rows("target_reviewed_words", "is_mature = 1") == 5
        assert reorder_logger.count_rows("global_reviewed_words", "is_mature = 1") == 5
        assert reorder_logger.count_rows("global_languages") == 2

        # check info

        assert reorder_logger.get_info_global() == {'en': {'num_words_mature': 3}, 'es': {'num_words_mature': 2}}

        per_target = reorder_logger.get_info_per_target()
        assert per_target['target1']['en'] == {'num_words_mature': 2}
        assert per_target['target1']['es'] == {'num_words_mature': 1}
        assert per_target['target2']['en'] == {'num_words_mature': 1}
        assert per_target['target2']['es'] == {'num_words_mature': 1}

        # reorder again

        event_logger = EventLogger()
        result = target_list.reorder_cards(col, event_logger)

        num_entries_added = reorder_logger.log_reordering(target_list, result)

        assert num_entries_added == 0
        assert reorder_logger.count_rows("reorders") == 1
        assert reorder_logger.count_rows("reordered_targets") == 2
        assert reorder_logger.count_rows("target_segments") == 4
        assert reorder_logger.count_rows("target_languages") == 4
        assert reorder_logger.count_rows("target_reviewed_words", "is_mature = 1") == 5
        assert reorder_logger.count_rows("global_reviewed_words", "is_mature = 1") == 5
        assert reorder_logger.count_rows("global_languages") == 2