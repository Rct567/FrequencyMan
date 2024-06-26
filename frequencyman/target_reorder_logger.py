"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from collections import defaultdict
import os
import sqlite3
from time import time
from typing import Any, Optional


from .lib.utilities import override, var_dump, var_dump_log
from .lib.sql_db_file import SqlDbFile
from .target_list import TargetList, TargetListReorderResult
from .tokenizers import LangId
from .target import Target, TargetReorderResult


class TargetReorderLogger(SqlDbFile):

    @override
    def _create_tables(self) -> None:

        self.query('''
            CREATE TABLE IF NOT EXISTS reorders (
                id INTEGER PRIMARY KEY,
                num_targets INTEGER,
                num_targets_reordered INTEGER,
                created_at INTEGER
            )
        ''')

        self.query('''
            CREATE TABLE IF NOT EXISTS targets (
                id TEXT PRIMARY KEY,
                reorder_id INTEGER,
                target_index INTEGER,
                num_cards INTEGER,
                num_new_cards INTEGER,
                num_cards_repositioned INTEGER,
                num_notes INTEGER,
                num_new_notes INTEGER
            )
        ''')

        self.query('''
        CREATE INDEX IF NOT EXISTS targets_reorder_id ON targets (reorder_id)
        ''')

        self.query('''
            CREATE TABLE IF NOT EXISTS target_segments (
                id INTEGER PRIMARY KEY,
                reorder_id INTEGER,
                target_id TEXT,
                segment_id TEXT,
                lang_id TEXT,
                num_words_new INTEGER,
                num_words_reviewed INTEGER,
                num_word_mature,
                words_familiarity_mean FLOAT,
                words_familiarity_median FLOAT,
                words_familiarity_max FLOAT
            )
        ''')
        self.query('''
        CREATE INDEX IF NOT EXISTS target_segments_reorder_id ON target_segments (reorder_id)
        ''')

        self.query('''
            CREATE TABLE IF NOT EXISTS target_languages (
                id INTEGER PRIMARY KEY,
                reorder_id INTEGER,
                target_id TEXT,
                lang_id TEXT,
                num_word_mature
            )
        ''')
        self.query('''
        CREATE INDEX IF NOT EXISTS target_languages_reorder_id ON target_languages (reorder_id)
        ''')

        self.commit()

    def log_reordering(self, targets: TargetList, target_reorder_result_list: TargetListReorderResult) -> int:

        assert len(targets) == len(target_reorder_result_list.reorder_result_list)

        reordered_targets_result = [target_reorder_result for target_reorder_result in target_reorder_result_list.reorder_result_list if target_reorder_result.num_cards_repositioned > 0]
        targets_with_id_str = [target for target in targets.target_list if target.id_str is not None]
        num_targets_reordered = len(reordered_targets_result)

        if len(targets_with_id_str) == 0:
            return 0

        if num_targets_reordered == 0 and self.count_rows("reorders") > 0:
            return 0

        result = self.query('''
            INSERT INTO reorders (
                num_targets, num_targets_reordered, created_at
            ) VALUES (
                ?, ?, ?
            )
        ''', (
            len(targets.target_list),
            num_targets_reordered,
            int(time())
        ))

        reorder_id = result.get_last_insert_id()
        num_entries_added = 0

        for (target_reorder_result, target) in zip(target_reorder_result_list.reorder_result_list, targets.target_list):
            if target.id_str is None:
                continue
            if self.__add_entry(reorder_id, target, target_reorder_result):
                num_entries_added += 1

        if num_entries_added == 0:
            self.delete_row("reorders", "id = ?", (reorder_id,))

        self.close()
        return num_entries_added

    def __add_entry(self, reorder_id: int, target: Target, target_reorder_result: TargetReorderResult) -> bool:

        if target_reorder_result.num_cards_repositioned == 0:
            num_entires_for_target = self.result("SELECT COUNT(*) FROM targets WHERE reorder_id = ?", (target.id_str,))
            if num_entires_for_target > 0:
                return False

        assert target.cache_data is not None
        assert target.cache_data['target_cards'] is not None
        assert target.cache_data['corpus'] is not None

        target_cards = target.get_cards()
        corpus_data = target.get_corpus_data(target_cards)

        # add log for reorder target

        self.query('''
            INSERT INTO targets (
                id, reorder_id, target_index, num_cards, num_new_cards, num_cards_repositioned,
                num_notes, num_new_notes
            ) VALUES (
                ?,?, ?, ?, ?, ?, ?, ?
            )
        ''', (
            target.id_str,
            reorder_id,
            target.index_num,
            len(target_cards.all_cards_ids),
            len(target_cards.new_cards),
            target_reorder_result.num_cards_repositioned,
            len(target_cards.all_cards_notes_ids),
            len(target_cards.new_cards_notes_ids),
        ))

        # add entry for each segment

        for segment_id, segment_data in corpus_data.content_metrics.items():

            self.query('''
                INSERT INTO target_segments (
                    reorder_id, target_id, segment_id, lang_id, num_words_new,num_words_reviewed,
                    num_word_mature, words_familiarity_mean, words_familiarity_median, words_familiarity_max
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            ''', (
                reorder_id,
                target.id_str,
                segment_id,
                str(segment_data.lang_id),
                0,
                len(segment_data.reviewed_words.keys()),
                len(segment_data.words_post_focus),
                segment_data.words_familiarity_mean,
                segment_data.words_familiarity_median,
                segment_data.words_familiarity_max,
            ))

        # add entry for each language

        focus_word_per_lang: dict[LangId, set[str]] = defaultdict(set)
        for segment_id, segment_data in corpus_data.content_metrics.items():
            focus_word_per_lang[segment_data.lang_id].update(segment_data.words_post_focus)

        for lang_id, focus_words in focus_word_per_lang.items():
            self.query('''
                INSERT INTO target_languages (
                    reorder_id, target_id, lang_id, num_word_mature
                ) VALUES (
                    ?, ?, ?, ?
                )
            ''', (
                reorder_id,
                target.id_str,
                str(lang_id),
                len(focus_words)
            ))

        self.commit()

        return True

    def get_latest_reorder_info(self) -> list[dict[str, Any]]:

        info = []

        result = self.query('''
            SELECT target_languages.*, targets.* FROM target_languages
            INNER JOIN targets ON targets.id = target_languages.target_id
            WHERE target_languages.reorder_id IN (SELECT MAX(id) FROM reorders)
        ''')

        for row in result.fetch_rows():
            info.append(row)

        return info
