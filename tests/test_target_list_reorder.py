import pytest

from frequencyman.card_ranker import CardRanker
from frequencyman.target_list import TargetList, TargetListReorderResult
from frequencyman.lib.event_logger import EventLogger

from tests.tools import TestCollections, freeze_time_anki


class TestTargetListReorder():

    @freeze_time_anki("2023-12-05")
    def test_reorder_cards_big_collection_es(self):

        col = TestCollections.get_test_collection('big_collection_es')

        target_list = TargetList(col.lang_data, col.cacher, col)

        target_list.set_targets([
            {
                'deck': 'Spanish',
                'notes': [{
                    "name": "-- My spanish --",
                    "fields": {
                        "Meaning": "EN",
                        "Sentence": "ES"
                    },
                }],
                'ideal_word_count': [2, 5]
            }
        ])

        assert len(target_list) == 1
        pre_sort_cards = target_list[0].get_cards_non_cached()

        # reorder cards
        event_logger = EventLogger()
        result = target_list.reorder_cards(col, event_logger)

        assert isinstance(result, TargetListReorderResult)
        assert len(result.reorder_result_list) == len(target_list)
        assert result.num_cards_repositioned == 6566
        assert result.num_targets_repositioned == 1
        assert len(result.modified_dirty_notes) == 7895

        # check result
        target_result = result.reorder_result_list[0]
        assert target_result.success
        assert target_result.cards_repositioned
        assert target_result.error is None
        assert len(target_result.sorted_cards_ids) == len(pre_sort_cards.new_cards_ids)
        assert target_result.sorted_cards_ids != pre_sort_cards.new_cards_ids
        assert target_result.sorted_cards_ids == target_list[0].get_cards_non_cached().new_cards_ids
        assert "Found 6566 new cards in a target collection of 15790 cards" in str(event_logger)
        assert "Repositioning 6566 cards" in str(event_logger)
        assert "Updating 7895 modified notes" in str(event_logger)

        # check focus word field for all notes
        notes_focus_words = []
        for note_id in col.find_notes('*'):
            note = col.get_note(note_id)
            notes_focus_words.append(str(note_id)+" => "+note['fm_focus_words'])

        col.lock_and_assert_result('notes_focus_words', notes_focus_words)

        # check acquired cards for each target
        assert len(target_list[0].get_cards_non_cached().all_cards_ids) == 15790
        assert len(target_list[0].get_cards_non_cached().get_notes_from_all_cards()) == 7895
        assert len(target_list[0].get_cards_non_cached().new_cards_ids) == 6566
        assert len(target_list[0].get_cards_non_cached().get_notes_from_new_cards()) == 4360

        # check order
        col.lock_and_assert_order('sorted_cards_ids', target_result.sorted_cards_ids)

    @freeze_time_anki("2023-12-01")
    def test_reorder_cards_big_collection_es_with_reorder_scope(self):

        col = TestCollections.get_test_collection('big_collection_es')

        target_list = TargetList(col.lang_data, col.cacher, col)

        target_list.set_targets([
            {
                'deck': 'Spanish',
                'notes': [{
                    "name": "-- My spanish --",
                    "fields": {
                        "Meaning": "EN",
                        "Sentence": "ES"
                    },
                }],
                "reorder_scope_query": "card:2",
                "ranking_factors": {
                    "familiarity": 1,
                    "lowest_word_frequency": 1
                }
            }
        ])

        assert len(target_list) == 1
        pre_sort_cards = target_list[0].get_cards_non_cached()

        # reorder cards
        event_logger = EventLogger()
        result = target_list.reorder_cards(col, event_logger)

        assert isinstance(result, TargetListReorderResult)
        assert len(result.reorder_result_list) == len(target_list)
        assert len(result.modified_dirty_notes) == 7895

        # check result
        target_result = result.reorder_result_list[0]
        assert target_result.success
        assert target_result.cards_repositioned
        assert target_result.error is None
        assert len(target_result.sorted_cards_ids) < len(pre_sort_cards.new_cards_ids)
        assert len(target_result.sorted_cards_ids) == 4223
        assert target_result.sorted_cards_ids != pre_sort_cards.new_cards_ids
        assert "Found 6566 new cards in a target collection of 15790 cards" in str(event_logger)
        assert "Reorder scope query reduced new cards from 6566 to 4223" in str(event_logger)
        assert "Repositioning 4223 cards" in str(event_logger)
        assert "Updating 7895 modified notes" in str(event_logger)

        # check acquired cards
        assert len(target_list[0].get_cards_non_cached().all_cards_ids) == 15790
        assert len(target_list[0].get_cards_non_cached().get_notes_from_all_cards()) == 7895
        assert len(target_list[0].get_cards_non_cached().new_cards_ids) == 6566
        assert len(target_list[0].get_cards_non_cached().get_notes_from_new_cards()) == 4360

        # check order
        col.lock_and_assert_order('sorted_cards_ids', target_result.sorted_cards_ids)

    @freeze_time_anki("2023-12-01")
    def test_two_deck_collection(self):

        col = TestCollections.get_test_collection('two_deck_collection')

        target_list = TargetList(col.lang_data, col.cacher, col)

        target_list.set_targets([
            {
                'deck': 'decka',
                'notes': [{
                    "name": "Basic",
                    "fields": {
                        "Front": "EN",
                        "Back": "ES"
                    },
                }]
            },
            {
                'deck': 'deckb',
                'notes': [{
                    "name": "Basic",
                    "fields": {
                        "Front": "EN",
                        "Back": "ES"
                    },
                }]
            }
        ])

        assert len(target_list) == 2

        # reorder cards
        event_logger = EventLogger()
        result = target_list.reorder_cards(col, event_logger)
        assert isinstance(result, TargetListReorderResult)
        assert len(result.reorder_result_list) == len(target_list) == result.num_targets_repositioned == 2

        # check result
        assert target_list[0].corpus_data is not None and len(target_list[0].corpus_data.segments_ids) == 2
        assert target_list[1].corpus_data is not None and len(target_list[1].corpus_data.segments_ids) == 2

        assert result.reorder_result_list[0].success and result.reorder_result_list[0].cards_repositioned
        assert result.reorder_result_list[0].error is None
        assert len(result.modified_dirty_notes) == 0
        assert "Reordering target #0" in str(event_logger)
        assert "Found 7 new cards in a target collection of 10 cards" in str(event_logger)
        assert "Reordering target #1" in str(event_logger)
        assert "Found 4 new cards in a target collection of 6 cards" in str(event_logger)

        assert result.num_cards_repositioned == 11
        assert result.reorder_result_list[0].num_cards_repositioned == 7
        assert result.reorder_result_list[1].num_cards_repositioned == 4

        # check acquired cards for each target
        assert len(target_list[0].get_cards_non_cached().all_cards_ids) == 10
        assert len(target_list[0].get_cards_non_cached().get_notes_from_all_cards()) == 10
        assert len(target_list[0].get_cards_non_cached().new_cards_ids) == 7
        assert len(target_list[0].get_cards_non_cached().get_notes_from_new_cards()) == 7
        assert len(target_list[1].get_cards_non_cached().all_cards_ids) == 6
        assert len(target_list[1].get_cards_non_cached().get_notes_from_all_cards()) == 6
        assert len(target_list[1].get_cards_non_cached().new_cards_ids) == 4
        assert len(target_list[1].get_cards_non_cached().get_notes_from_new_cards()) == 4

        # check order
        col.lock_and_assert_order('sorted_cards_ids_0', result.reorder_result_list[0].sorted_cards_ids)
        col.lock_and_assert_order('sorted_cards_ids_1', result.reorder_result_list[1].sorted_cards_ids)

        # reorder again
        event_logger = EventLogger()
        result = target_list.reorder_cards(col, event_logger)
        assert "Repositioning 7 cards not needed for this target." in str(event_logger)
        assert "Repositioning 4 cards not needed for this target." in str(event_logger)
        assert result.num_targets_repositioned == 0
        assert result.num_cards_repositioned == 0

        # check focus words in corpus data
        focus_words: dict[str, list] = {}
        for target in target_list.target_list:
            if target.corpus_data and target.corpus_data.content_metrics:
                for segment_id, segment_data in target.corpus_data.content_metrics.items():
                    focus_words[str(target.index_num)+'_'+str(segment_id)] = sorted(segment_data.mature_words)
        col.lock_and_assert_result('focus_words', focus_words)

    @freeze_time_anki("2023-12-01")
    def test_two_deck_collection_with_ignore_list(self):

        col = TestCollections.get_test_collection('two_deck_collection')

        target_list = TargetList(col.lang_data, col.cacher, col)

        target_list.set_targets([
            {
                'decks': 'decka, deckb',
                'notes': [{
                    "name": "Basic",
                    "fields": {
                        "Front": "EN_with_ignore",
                        "Back": "ES_with_ignore"
                    },
                }],
                'ideal_word_count': [2, 5]
            }
        ])

        assert len(target_list) == 1

        # reorder cards
        event_logger = EventLogger()
        result = target_list.reorder_cards(col, event_logger)

        # check result
        assert target_list[0].corpus_data is not None and len(target_list[0].corpus_data.segments_ids) == 2

        assert result.num_cards_repositioned == 11
        reorder_result = result.reorder_result_list[0]
        assert reorder_result.success and reorder_result.cards_repositioned
        assert reorder_result.error is None
        assert len(result.modified_dirty_notes) == 0
        assert "Reordering target #0" in str(event_logger)
        assert "Found 11 new cards in a target collection of 16 cards" in str(event_logger)
        assert "11 cards repositioned" in str(event_logger)

        # check order
        col.lock_and_assert_order('sorted_cards_ids', result.reorder_result_list[0].sorted_cards_ids)

    @freeze_time_anki("2023-12-01")
    def test_two_deck_collection_with_reorder_scope(self):

        col = TestCollections.get_test_collection('two_deck_collection')

        target_list = TargetList(col.lang_data, col.cacher, col)

        target_list.set_targets([
            {
                'decks': 'decka, deckb',
                'notes': [{
                    "name": "Basic",
                    "fields": {
                        "Front": "EN",
                        "Back": "ES"
                    },
                }],
                'reorder_scope_query': 'deck:decka'
            },
            {
                'decks': 'decka, deckb',
                'notes': [{
                    "name": "Basic",
                    "fields": {
                        "Front": "EN",
                        "Back": "ES"
                    },
                }],
                'reorder_scope_query': 'deck:deckb'
            }
        ])

        assert len(target_list) == 2

        # reorder cards
        event_logger = EventLogger()
        result = target_list.reorder_cards(col, event_logger)
        assert isinstance(result, TargetListReorderResult)
        assert len(result.reorder_result_list) == len(target_list)

        # check result
        assert target_list[0].corpus_data is not None and len(target_list[0].corpus_data.segments_ids) == 2
        assert target_list[1].corpus_data is None  # was cached

        reorder_result = result.reorder_result_list[0]
        assert reorder_result.success and reorder_result.cards_repositioned
        assert reorder_result.error is None
        assert len(result.modified_dirty_notes) == 0

        assert "Reordering target #0" in str(event_logger)
        assert "Reorder scope query reduced new cards from 11 to 7." in str(event_logger)

        assert "Reordering target #1" in str(event_logger)
        assert "Reorder scope query reduced new cards from 11 to 4." in str(event_logger)

        assert "Found 11 new cards in a target collection of 16 cards." in str(event_logger)

        assert result.reorder_result_list[0].num_cards_repositioned == 7
        assert result.reorder_result_list[1].num_cards_repositioned == 4
        assert result.num_cards_repositioned == 11

        # check acquired cards for each target
        assert len(target_list[0].get_cards_non_cached().all_cards_ids) == 16
        assert len(target_list[0].get_cards_non_cached().get_notes_from_all_cards()) == 16
        assert len(target_list[0].get_cards_non_cached().new_cards_ids) == 11
        assert len(target_list[0].get_cards_non_cached().get_notes_from_new_cards()) == 11
        assert len(target_list[1].get_cards_non_cached().all_cards_ids) == 16
        assert len(target_list[1].get_cards_non_cached().get_notes_from_all_cards()) == 16
        assert len(target_list[1].get_cards_non_cached().new_cards_ids) == 11
        assert len(target_list[1].get_cards_non_cached().get_notes_from_new_cards()) == 11

        # check order
        col.lock_and_assert_order('sorted_cards_ids_0', result.reorder_result_list[0].sorted_cards_ids)
        col.lock_and_assert_order('sorted_cards_ids_1', result.reorder_result_list[1].sorted_cards_ids)

    @freeze_time_anki("2023-12-01")
    def test_two_deck_collection_no_reviewed_cards(self):

        col = TestCollections.get_test_collection('two_deck_collection')

        # reset all cards
        all_card_ids = col.find_cards('*')
        col.sched.reset_cards(list(all_card_ids))

        target_list = TargetList(col.lang_data, col.cacher, col)

        target_list.set_targets([
            {
                'decks': 'decka, deckb',
                'notes': [{
                    "name": "Basic",
                    "fields": {
                        "Front": "EN",
                        "Back": "EN"
                    },
                }],
                'ideal_word_count': [2, 5],
                'ranking_proper_introduction_dispersed': 0.5,
                'reorder_scope_query': 'deck:decka'
            }
        ])

        # reorder cards
        event_logger = EventLogger()
        result = target_list.reorder_cards(col, event_logger)

        # check result
        assert target_list[0].corpus_data is not None and len(target_list[0].corpus_data.segments_ids) == 1

        reorder_result = result.reorder_result_list[0]
        assert reorder_result.success and reorder_result.cards_repositioned
        assert reorder_result.error is None
        assert len(result.modified_dirty_notes) == 0

        assert "Reordering target #0" in str(event_logger)
        assert "Found 16 new cards in a target collection of 16 cards." in str(event_logger)
        assert "Reorder scope query reduced new cards from 16 to 10." in str(event_logger)

        assert result.reorder_result_list[0].num_cards_repositioned == 10
        assert result.num_cards_repositioned == 10

        assert len(target_list[0].get_cards_non_cached().all_cards_ids) == 16
        assert len(target_list[0].get_cards_non_cached().get_notes_from_all_cards()) == 16
        assert len(target_list[0].get_cards_non_cached().new_cards_ids) == 16
        assert len(target_list[0].get_cards_non_cached().get_notes_from_new_cards()) == 16

        # check order
        col.lock_and_assert_order('sorted_cards_ids', result.reorder_result_list[0].sorted_cards_ids)

    @freeze_time_anki("2023-12-01")
    def test_two_deck_collection_no_cards(self):

        col = TestCollections.get_test_collection('two_deck_collection')

        # remove all notes
        col.remove_notes(list(col.find_notes('*')))

        target_list = TargetList(col.lang_data, col.cacher, col)

        target_list.set_targets([
            {
                'decks': 'decka, deckb',
                'notes': [{
                    "name": "Basic",
                    "fields": {
                        "Front": "EN",
                        "Back": "EN"
                    },
                }],
                'reorder_scope_query': 'deck:decka'
            }
        ])

        # reorder cards
        event_logger = EventLogger()
        result = target_list.reorder_cards(col, event_logger)

        # check result

        reorder_result = result.reorder_result_list[0]
        assert not (reorder_result.success and reorder_result.cards_repositioned)
        assert reorder_result.error is not None

        assert "no new cards" in str(event_logger)
        assert "0 cards repositioned" in str(event_logger)

        assert result.reorder_result_list[0].num_cards_repositioned == 0
        assert result.num_cards_repositioned == 0

        assert len(target_list[0].get_cards_non_cached().all_cards_ids) == 0
        assert len(target_list[0].get_cards_non_cached().get_notes_from_all_cards()) == 0
        assert len(target_list[0].get_cards_non_cached().new_cards_ids) == 0
        assert len(target_list[0].get_cards_non_cached().get_notes_from_new_cards()) == 0

    @freeze_time_anki("2023-12-01")
    def test_two_deck_collection_corpus_segmentation_by_note_field(self):

        col = TestCollections.get_test_collection('two_deck_collection')

        target_list = TargetList(col.lang_data, col.cacher, col)

        target_list.set_targets([
            {
                'decks': ['decka', 'deckb'],
                'notes': [{
                    "name": "Basic",
                    "fields": {
                        "Front": "EN",
                        "Back": "EN"
                    },
                }],
                "corpus_segmentation_strategy": "by_note_model_id_and_field_name"
            }
        ])

        assert len(target_list) == 1

        # reorder cards
        event_logger = EventLogger()
        result = target_list.reorder_cards(col, event_logger)

        # check result
        assert target_list[0].corpus_data is not None
        assert len(target_list[0].corpus_data.segments_ids) == 2
        assert len(target_list[0].corpus_data.content_metrics.keys()) == 2

        reorder_result = result.reorder_result_list[0]
        assert reorder_result.success and reorder_result.cards_repositioned
        assert reorder_result.error is None
        assert len(result.modified_dirty_notes) == 0
        assert "Found 11 new cards in a target collection of 16 cards" in str(event_logger)

        assert result.reorder_result_list[0].num_cards_repositioned == 11
        assert result.num_cards_repositioned == 11

        # check order
        col.lock_and_assert_order('sorted_cards_ids', result.reorder_result_list[0].sorted_cards_ids)

    @freeze_time_anki("2023-12-01")
    def test_two_deck_collection_low_familiarity(self):

        col = TestCollections.get_test_collection('two_deck_collection_low_fam')

        target_list = TargetList(col.lang_data, col.cacher, col)

        target_list.set_targets([
            {
                'decks': 'decka, deckb',
                'notes': [{
                    "name": "Basic",
                    "fields": {
                        "Front": "EN",
                        "Back": "EN"
                    },
                }]
            }
        ])

        # reorder cards
        event_logger = EventLogger()
        result = target_list.reorder_cards(col, event_logger)

        # check result
        assert target_list[0].corpus_data is not None and len(target_list[0].corpus_data.segments_ids) == 1

        reorder_result = result.reorder_result_list[0]
        assert reorder_result.success and reorder_result.cards_repositioned
        assert reorder_result.error is None
        assert len(result.modified_dirty_notes) == 0

        assert "Reordering target #0" in str(event_logger)
        assert "Found 12 new cards in a target collection of 16 cards." in str(event_logger)

        assert result.reorder_result_list[0].num_cards_repositioned == 12
        assert result.num_cards_repositioned == 12

        assert len(target_list[0].get_cards_non_cached().all_cards_ids) == 16
        assert len(target_list[0].get_cards_non_cached().get_notes_from_all_cards()) == 16
        assert len(target_list[0].get_cards_non_cached().new_cards_ids) == 12
        assert len(target_list[0].get_cards_non_cached().get_notes_from_new_cards()) == 12

        # check order
        col.lock_and_assert_order('sorted_cards_ids', result.reorder_result_list[0].sorted_cards_ids)

    @freeze_time_anki("2023-12-01")
    def test_two_deck_collection_every_factor(self):

        for ranking_factor in CardRanker. get_default_ranking_factors_span().keys():

            col = TestCollections.get_test_collection('two_deck_collection')

            target_list = TargetList(col.lang_data, col.cacher, col)

            target_list.set_targets([
                {
                    'decks': ['decka', 'deckb'],
                    'notes': [{
                        "name": "Basic",
                        "fields": {
                            "Front": "EN",
                            "Back": "EN"
                        },
                    }],
                    'ranking_factors': {ranking_factor: 1}
                }
            ])

            # reorder cards
            event_logger = EventLogger()
            result = target_list.reorder_cards(col, event_logger)

            reorder_result = result.reorder_result_list[0]
            assert reorder_result.success and reorder_result.error is None

            assert len(target_list[0].get_cards_non_cached().all_cards_ids) == 16

            col.lock_and_assert_order('all_cards_ids_'+ranking_factor, target_list[0].get_cards_non_cached().all_cards_ids)

            col.close()
