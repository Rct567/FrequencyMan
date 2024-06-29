"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from collections import defaultdict
from time import time

from aqt import Union

from .lib.utilities import override, var_dump, var_dump_log
from .lib.sql_db_file import SqlDbFile
from .target_list import TargetList, TargetListReorderResult
from .tokenizers import LangId
from .target import Target, TargetReorderResult


class TargetReorderLogger(SqlDbFile):

    targets_languages: set[LangId] = set()

    @override
    def __init__(self, db_file: str):
        super().__init__(db_file)
        self.targets_languages = set()

    @override
    def _create_tables(self) -> None:

        self.create_table('reorders', {
            'id': 'INTEGER PRIMARY KEY',
            'num_targets': 'INTEGER',
            'num_targets_reordered': 'INTEGER',
            'created_at': 'INTEGER'
        })

        self.create_table('reordered_targets', {
            'id': 'TEXT',
            'reorder_id': 'INTEGER',
            'target_index': 'INTEGER',
            'num_cards': 'INTEGER',
            'num_new_cards': 'INTEGER',
            'num_cards_repositioned': 'INTEGER',
            'num_notes': 'INTEGER',
            'num_new_notes': 'INTEGER'
        }, constraints='UNIQUE(reorder_id, id) ON CONFLICT FAIL')
        self.create_index('reordered_targets', 'reordered_targets_reorder_id', ['reorder_id'])

        self.create_table('target_segments', {
            'id': 'INTEGER PRIMARY KEY',
            'reorder_id': 'INTEGER',
            'target_id': 'TEXT',
            'segment_id': 'TEXT',
            'lang_id': 'TEXT',
            'num_words_new': 'INTEGER',
            'num_words_reviewed': 'INTEGER',
            'num_words_mature': 'INTEGER',
            'words_familiarity_mean': 'FLOAT',
            'words_familiarity_median': 'FLOAT',
            'words_familiarity_max': 'FLOAT'
        }, constraints='UNIQUE(reorder_id, target_id, segment_id) ON CONFLICT FAIL')
        self.create_index('target_segments', 'target_segments_reorder_id', ['reorder_id'])

        self.create_table('target_mature_words', {
            'target_id': 'TEXT',
            'lang_id': 'TEXT',
            'word': 'TEXT',
            'familiarity': 'FLOAT'
        }, constraints='UNIQUE(target_id, lang_id, word) ON CONFLICT REPLACE')
        self.create_index('target_mature_words', 'target_mature_words_target_id', ['target_id'])

        self.create_table('target_languages', {
            'reorder_id': 'INTEGER',
            'target_id': 'TEXT',
            'lang_id': 'TEXT',
            'num_words_mature': 'INTEGER'
        }, constraints='UNIQUE(reorder_id, target_id, lang_id) ON CONFLICT REPLACE')
        self.create_index('target_languages', 'target_languages_reorder_id', ['reorder_id'])

        self.create_table('global_languages', {
            'lang_id': 'TEXT',
            'num_words_mature': 'INTEGER',
            'reorder_id': 'INTEGER',
            'date_created': 'INTEGER'
        }, constraints='UNIQUE(reorder_id, lang_id) ON CONFLICT FAIL')

        self.create_table('global_mature_words', {
            'lang_id': 'TEXT',
            'word': 'TEXT',
            'familiarity': 'FLOAT DEFAULT 0.0',
            'date_created': 'INTEGER'
        }, constraints='UNIQUE(lang_id, word) ON CONFLICT IGNORE')
        self.create_index('global_mature_words', 'global_mature_words_lang_id', ['lang_id'])

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

        result = self.insert_row('reorders', {
            'num_targets': len(targets.target_list),
            'num_targets_reordered': num_targets_reordered,
            'created_at': int(time())
        })

        reorder_id = result.get_last_insert_id()
        num_entries_added = 0

        for (target_reorder_result, target) in zip(target_reorder_result_list.reorder_result_list, targets.target_list):
            if target.id_str is None:
                continue
            if self.__add_entry(reorder_id, target, target_reorder_result):
                num_entries_added += 1

        if num_entries_added == 0:
            self.delete_row("reorders", "id = ?", reorder_id)
        else:

            # update familiarity for each word

            languages_str = ', '.join(['"'+str(lang_id)+'"' for lang_id in self.targets_languages])
            self.query('''UPDATE global_mature_words SET familiarity = (
                SELECT MAX(target_mature_words.familiarity) FROM target_mature_words
                WHERE target_mature_words.lang_id = global_mature_words.lang_id AND target_mature_words.word = global_mature_words.word
            ) WHERE lang_id IN ({})'''.format(languages_str))

             # update num_words_mature for each language

            for lang_id in self.targets_languages:
                num_words_mature = self.result('SELECT COUNT(*) FROM global_mature_words WHERE global_mature_words.lang_id = ?', str(lang_id))
                self.insert_row('global_languages', {'lang_id': str(lang_id), 'num_words_mature': num_words_mature, 'reorder_id': reorder_id, 'date_created': int(time())})

        if self.in_transaction():
            self.commit()

        self.close()
        return num_entries_added

    def __add_entry(self, reorder_id: int, target: Target, target_reorder_result: TargetReorderResult) -> bool:

        if target.id_str is None:
            return False

        if target_reorder_result.num_cards_repositioned == 0:
            num_entires_for_target = self.result("SELECT COUNT(*) FROM reordered_targets WHERE reorder_id = ?", reorder_id)
            if num_entires_for_target > 0:
                return False

        assert target.cache_data is not None
        assert target.cache_data['target_cards'] is not None
        assert target.cache_data['corpus'] is not None

        target_cards = target.get_cards()
        corpus_data = target.get_corpus_data(target_cards)

        # add entry for reordered target

        self.insert_row('reordered_targets', {
            'id': target.id_str,
            'reorder_id': reorder_id,
            'target_index': target.index_num,
            'num_cards': len(target_cards.all_cards_ids),
            'num_new_cards': len(target_cards.new_cards),
            'num_cards_repositioned': target_reorder_result.num_cards_repositioned,
            'num_notes': len(target_cards.all_cards_notes_ids),
            'num_new_notes': len(target_cards.new_cards_notes_ids),
        })

        # add entry for each segment in target

        for segment_id, segment_data in corpus_data.content_metrics.items():

            self.targets_languages.add(segment_data.lang_id)

            self.insert_row('target_segments', {
                'reorder_id': reorder_id,
                'target_id': target.id_str,
                'segment_id': segment_id,
                'lang_id': str(segment_data.lang_id),
                'num_words_new': 0,
                'num_words_reviewed': len(segment_data.reviewed_words.keys()),
                'num_words_mature': len(segment_data.words_post_focus),
                'words_familiarity_mean': segment_data.words_familiarity_mean,
                'words_familiarity_median': segment_data.words_familiarity_median,
                'words_familiarity_max': segment_data.words_familiarity_max
            })

        # add entry for each language in target

        target_mature_words_per_lang: dict[LangId, set[str]] = defaultdict(set)
        target_mature_words: list[tuple[str, str, str, float]] = []

        for segment_id, segment_data in corpus_data.content_metrics.items():

            target_mature_words_per_lang[segment_data.lang_id].update(segment_data.words_post_focus)

            for word in segment_data.words_post_focus:
                target_mature_words.append((target.id_str, str(segment_data.lang_id), word, segment_data.words_familiarity[word]))

        for lang_id, mature_words in target_mature_words_per_lang.items():
            self.insert_row('target_languages',
                {'reorder_id': reorder_id, 'target_id': target.id_str, 'lang_id': str(lang_id), 'num_words_mature': len(mature_words)}
            )

        if target_mature_words:

            self.insert_many_rows('target_mature_words',
                ({'target_id': target.id_str, 'lang_id': word[1], 'word': word[2], 'familiarity': word[3]} for word in target_mature_words)
            )

            self.insert_many_rows('global_mature_words',
                ({'lang_id': word[1], 'word': word[2], 'date_created': int(time())} for word in target_mature_words)
            )

        # done with entry for target

        return True

    def get_info_global(self) -> dict[str, dict[str, int]]:

        info: dict[str, dict] = {}

        result = self.query('SELECT lang_id, num_words_mature FROM global_languages GROUP BY lang_id ORDER BY date_created DESC')

        for row in result.fetch_rows():
            info[row['lang_id']] = {'num_words_mature': row['num_words_mature']}

        return info

    def get_info_per_target(self) -> dict[str, dict[str, dict[str, Union[int, str]]]]:

        info_per_target = defaultdict(dict)

        result = self.query('''
            SELECT a.* FROM target_languages AS a
            INNER JOIN reordered_targets ON reordered_targets.reorder_id = a.reorder_id
            INNER JOIN reorders ON reorders.id = a.reorder_id
			WHERE a.reorder_id IN (SELECT MAX(b.reorder_id) FROM target_languages AS b WHERE b.lang_id = a.lang_id AND b.target_id = a.target_id)
            ORDER BY reorders.created_at DESC''')

        for row in result.fetch_rows():
            info_per_target[row['target_id']][row['lang_id']] = {'num_words_mature': row['num_words_mature']}

        return info_per_target
