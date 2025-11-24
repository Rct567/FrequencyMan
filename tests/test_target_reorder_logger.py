from pathlib import Path
from collections.abc import Generator
import pytest

from frequencyman.target_list import TargetList
from frequencyman.lib.event_logger import EventLogger
from frequencyman.reorder_logger import ReorderLogger, SqlDbFile

from tests.tools import TestCollection, TestCollectionFixture, freeze_time_anki, with_test_collection, test_collection
col: TestCollectionFixture = test_collection

TEST_DATA_DIR = Path(__file__).parent / 'data'


@pytest.fixture
def reorder_logger(tmpdir: str) -> Generator[ReorderLogger, None, None]:
    db_path = Path(tmpdir) / 'test_reorder_log.sqlite'
    # db_path = Path(TEST_DATA_DIR) / 'test_reorder_log.sqlite'
    if db_path.exists():
        db_path.unlink()
    reorder_logger = ReorderLogger(SqlDbFile(db_path))
    yield reorder_logger
    reorder_logger.close()


class TestTargetReorderLogger:

    @freeze_time_anki("2023-12-01")
    @with_test_collection("two_deck_collection")
    def test_reorder_logger(self, col: TestCollection, reorder_logger: ReorderLogger) -> None:

        targets: list = [
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
        ]

        target_list = TargetList(col.lang_data, col.cacher, col)
        target_list.set_targets(targets)

        result = target_list.reorder_cards(col, EventLogger())

        num_entries_added = reorder_logger.log_reordering(target_list, result)

        assert num_entries_added == 2
        assert reorder_logger.db.count_rows("reorders") == 1
        assert reorder_logger.db.count_rows("reordered_targets") == 2
        assert reorder_logger.db.count_rows("target_segments") == 4
        assert reorder_logger.db.count_rows("target_languages") == 4
        assert reorder_logger.db.count_rows("target_reviewed_words", "is_mature > 0") == 5
        assert reorder_logger.db.count_rows("global_reviewed_words", "is_mature > 0") == 5
        assert reorder_logger.db.count_rows("global_languages") == 2

        # check info

        assert reorder_logger.get_info_global()['en'] == {'num_words_mature': 3, 'num_words_reviewed': 7, 'num_words_learning': 4}
        assert reorder_logger.get_info_global()['es'] == {'num_words_mature': 2, 'num_words_reviewed': 3, 'num_words_learning': 1}

        per_target = reorder_logger.get_info_per_target()
        assert per_target['target1']['en'] == {'num_words_mature': 2, 'num_words_reviewed': 4, 'num_words_learning': 2}
        assert per_target['target1']['es'] == {'num_words_mature': 1, 'num_words_reviewed': 1, 'num_words_learning': 0}
        assert per_target['target2']['en'] == {'num_words_mature': 1, 'num_words_reviewed': 4, 'num_words_learning': 3}
        assert per_target['target2']['es'] == {'num_words_mature': 1, 'num_words_reviewed': 2, 'num_words_learning': 1}

        # reorder again, test skipping of new log entry

        result = target_list.reorder_cards(col, EventLogger())

        num_entries_added = reorder_logger.log_reordering(target_list, result)

        assert result.num_targets_repositioned == 0
        assert num_entries_added == 0
        assert reorder_logger.db.count_rows("reorders") == 1
        assert reorder_logger.db.count_rows("reordered_targets") == 2
        assert reorder_logger.db.count_rows("target_segments") == 4
        assert reorder_logger.db.count_rows("target_languages") == 4
        assert reorder_logger.db.count_rows("target_reviewed_words", "is_mature > 0") == 5
        assert reorder_logger.db.count_rows("global_reviewed_words", "is_mature > 0") == 5
        assert reorder_logger.db.count_rows("global_languages") == 2

        # reorder again, force new log entry

        targets[0]['ranking_word_frequency'] = 10.0
        targets[1]['ranking_word_frequency'] = 10.0

        target_list = TargetList(col.lang_data, col.cacher, col)
        target_list.set_targets(targets)

        result = target_list.reorder_cards(col, EventLogger())
        assert result.num_targets_repositioned == 2

        num_entries_added = reorder_logger.log_reordering(target_list, result)

        assert num_entries_added == 2
        assert reorder_logger.db.count_rows("reorders") == 2
        assert reorder_logger.db.count_rows("reordered_targets") == 4
        assert reorder_logger.db.count_rows("target_segments") == 8
        assert reorder_logger.db.count_rows("target_languages") == 8
        assert reorder_logger.db.count_rows("target_reviewed_words", "is_mature > 0") == 5
        assert reorder_logger.db.count_rows("global_reviewed_words", "is_mature > 0") == 5
        assert reorder_logger.db.count_rows("global_languages") == 4

        # reset all cards, reorder and check results

        all_card_ids = col.find_cards('*')
        col.sched.reset_cards(list(all_card_ids))

        target_list = TargetList(col.lang_data, col.cacher, col)
        target_list.set_targets(targets)

        result = target_list.reorder_cards(col, EventLogger())
        assert result.num_targets_repositioned == 2

        num_entries_added = reorder_logger.log_reordering(target_list, result)

        assert num_entries_added == 2
        assert reorder_logger.db.count_rows("reorders") == 3

        per_target = reorder_logger.get_info_per_target()
        assert per_target['target1']['en'] == {'num_words_mature': 0, 'num_words_reviewed': 0, 'num_words_learning': 0}
        assert per_target['target1']['es'] == {'num_words_mature': 0, 'num_words_reviewed': 0, 'num_words_learning': 0}
        assert per_target['target2']['en'] == {'num_words_mature': 0, 'num_words_reviewed': 0, 'num_words_learning': 0}
        assert per_target['target2']['es'] == {'num_words_mature': 0, 'num_words_reviewed': 0, 'num_words_learning': 0}

        global_info = reorder_logger.get_info_global()
        assert global_info['en'] == {'num_words_mature': 0, 'num_words_reviewed': 0, 'num_words_learning': 0}
        assert global_info['es'] == {'num_words_mature': 0, 'num_words_reviewed': 0, 'num_words_learning': 0}
