import pytest

from frequencyman.target_list import TargetList, TargetListReorderResult
from frequencyman.lib.event_logger import EventLogger
from frequencyman.language_data import LangDataId, LanguageData

from anki.collection import Collection, OpChanges, OpChangesWithCount

from anki.cards import CardId, Card
from anki.notes import Note, NoteId

from tests.tools import TestCollections



class TestTargetListReorder():

    def test_reorder_cards_big_collection_es(self):


        col, lang_data, assert_locked_order = TestCollections.get_test_collection('big_collection_es')

        target_list = TargetList(lang_data, col)

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
        pre_sort_cards = target_list[0].get_cards()

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
        assert len(target_result.sorted_cards_ids) == len(pre_sort_cards.new_cards_ids)
        assert target_result.sorted_cards_ids != pre_sort_cards.new_cards_ids
        assert target_result.sorted_cards_ids == target_list[0].get_cards().new_cards_ids
        assert "Found 6566 new cards in a target collection of 15790 cards" in str(event_logger)
        assert "Repositioning 6566 cards" in str(event_logger)
        assert "Updating 7895 modified notes" in str(event_logger)

        # check value of focus words
        assert col.get_note(NoteId(1548089874907))['fm_focus_words'] == '<span id="fm_focus_words"><span data-field-index="0">ajedrez, jugamos</span> <span class="separator">/</span> <span data-field-index="1">chess</span></span>'
        assert col.get_note(NoteId(1548089876496))['fm_focus_words'] == '<span id="fm_focus_words"><span data-field-index="0">fotografías</span></span>'
        assert col.get_note(NoteId(1671840154010))['fm_focus_words'] == '<span id="fm_focus_words"><span data-field-index="0">hacerlas</span> <span class="separator">/</span> <span data-field-index="1">efficient, pleasure</span></span>'

        # these should not have focus words
        notes_empty_focus_words = {1678410313201, 1548089872580, 1695675879863, 1695675879703, 1687208310219,
                                   1548089874025, 1546160205490, 1548089878113, 1651511363702}
        for note_id in notes_empty_focus_words:
            assert col.get_note(NoteId(note_id))['fm_focus_words'] == "", note_id

        # these should have focus words
        notes_none_empty_focus_word = {1548089873399, 1548089879591, 1562346819967, 1546959316161, 1562346819250,
                                       1548089877279, 1548089878563, 1548089878527}
        for note_id in notes_none_empty_focus_word:
            assert len(col.get_note(NoteId(note_id))['fm_focus_words']) > 7, note_id

        # check acquired cards for each target
        assert len(target_list[0].get_cards().all_cards_ids) == 15790
        assert len(target_list[0].get_cards().get_notes_from_all_cards()) == 7895
        assert len(target_list[0].get_cards().new_cards_ids) == 6566
        assert len(target_list[0].get_cards().get_notes_from_new_cards()) == 4360

        # check order
        assert_locked_order(target_result.sorted_cards_ids)

    def test_reorder_cards_big_collection_es_with_reorder_scope(self):

        col, lang_data, assert_locked_order = TestCollections.get_test_collection('big_collection_es')

        target_list = TargetList(lang_data, col)

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
        pre_sort_cards = target_list[0].get_cards()

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
        assert len(target_list[0].get_cards().all_cards_ids) == 15790
        assert len(target_list[0].get_cards().get_notes_from_all_cards()) == 7895
        assert len(target_list[0].get_cards().new_cards_ids) == 6566
        assert len(target_list[0].get_cards().get_notes_from_new_cards()) == 4360

        # check order
        assert_locked_order(target_result.sorted_cards_ids)

    def test_two_deck_collection(self):

        col, language_data, assert_locked_order = TestCollections.get_test_collection('two_deck_collection')

        target_list = TargetList(language_data, col)

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
        assert len(result.reorder_result_list) == len(target_list)

        # check result
        assert target_list[0].target_corpus_data is not None and len(target_list[0].target_corpus_data.data_segments) == 2
        assert target_list[1].target_corpus_data is not None and len(target_list[1].target_corpus_data.data_segments) == 2


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
        assert len(target_list[0].get_cards().all_cards_ids) == 10
        assert len(target_list[0].get_cards().get_notes_from_all_cards()) == 10
        assert len(target_list[0].get_cards().new_cards_ids) == 7
        assert len(target_list[0].get_cards().get_notes_from_new_cards()) == 7
        assert len(target_list[1].get_cards().all_cards_ids) == 6
        assert len(target_list[1].get_cards().get_notes_from_all_cards()) == 6
        assert len(target_list[1].get_cards().new_cards_ids) == 4
        assert len(target_list[1].get_cards().get_notes_from_new_cards()) == 4

        # check order
        assert_locked_order(result.reorder_result_list[0].sorted_cards_ids+result.reorder_result_list[1].sorted_cards_ids)

    def test_two_deck_collection_with_ignore_list(self):

        col, language_data, assert_locked_order = TestCollections.get_test_collection('two_deck_collection')

        target_list = TargetList(language_data, col)

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
        assert target_list[0].target_corpus_data is not None and len(target_list[0].target_corpus_data.data_segments) == 2

        assert result.num_cards_repositioned == 11
        reorder_result = result.reorder_result_list[0]
        assert reorder_result.success and reorder_result.cards_repositioned
        assert reorder_result.error is None
        assert len(result.modified_dirty_notes) == 0
        assert "Reordering target #0" in str(event_logger)
        assert "Found 11 new cards in a target collection of 16 cards" in str(event_logger)
        assert "11 cards repositioned" in str(event_logger)

        # check order
        assert_locked_order(result.reorder_result_list[0].sorted_cards_ids)

    def test_two_deck_collection_with_reorder_scope(self):

        col, language_data, assert_locked_order = TestCollections.get_test_collection('two_deck_collection')

        target_list = TargetList(language_data, col)

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
        assert target_list[0].target_corpus_data is not None and len(target_list[0].target_corpus_data.data_segments) == 2
        assert target_list[1].target_corpus_data is None # was cached

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
        assert len(target_list[0].get_cards().all_cards_ids) == 16
        assert len(target_list[0].get_cards().get_notes_from_all_cards()) == 16
        assert len(target_list[0].get_cards().new_cards_ids) == 11
        assert len(target_list[0].get_cards().get_notes_from_new_cards()) == 11
        assert len(target_list[1].get_cards().all_cards_ids) == 16
        assert len(target_list[1].get_cards().get_notes_from_all_cards()) == 16
        assert len(target_list[1].get_cards().new_cards_ids) == 11
        assert len(target_list[1].get_cards().get_notes_from_new_cards()) == 11

        # check order
        assert_locked_order(result.reorder_result_list[0].sorted_cards_ids+result.reorder_result_list[1].sorted_cards_ids)

    def test_two_deck_collection_no_reviewed_cards(self):

        col, language_data, assert_locked_order = TestCollections.get_test_collection('two_deck_collection')

        # reset all cards
        all_card_ids = col.find_cards('*')
        col.sched.reset_cards(list(all_card_ids))

        target_list = TargetList(language_data, col)

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
                'reorder_scope_query': 'deck:decka'
            }
        ])

        # reorder cards
        event_logger = EventLogger()
        result = target_list.reorder_cards(col, event_logger)

        # check result
        assert target_list[0].target_corpus_data is not None and len(target_list[0].target_corpus_data.data_segments) == 1

        reorder_result = result.reorder_result_list[0]
        assert reorder_result.success and reorder_result.cards_repositioned
        assert reorder_result.error is None
        assert len(result.modified_dirty_notes) == 0

        assert "Reordering target #0" in str(event_logger)
        assert "Found 16 new cards in a target collection of 16 cards." in str(event_logger)
        assert "Reorder scope query reduced new cards from 16 to 10." in str(event_logger)

        assert result.reorder_result_list[0].num_cards_repositioned == 10
        assert result.num_cards_repositioned == 10

        assert len(target_list[0].get_cards().all_cards_ids) == 16
        assert len(target_list[0].get_cards().get_notes_from_all_cards()) == 16
        assert len(target_list[0].get_cards().new_cards_ids) == 16
        assert len(target_list[0].get_cards().get_notes_from_new_cards()) == 16

        # check order
        assert_locked_order(result.reorder_result_list[0].sorted_cards_ids)

    def test_two_deck_collection_corpus_segmentation_by_note_field(self):

        col, language_data, assert_locked_order = TestCollections.get_test_collection('two_deck_collection')

        target_list = TargetList(language_data, col)

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
        assert target_list[0].target_corpus_data is not None
        assert len(target_list[0].target_corpus_data.data_segments) == 2
        assert len(target_list[0].target_corpus_data.content_metrics.keys()) == 2

        reorder_result = result.reorder_result_list[0]
        assert reorder_result.success and reorder_result.cards_repositioned
        assert reorder_result.error is None
        assert len(result.modified_dirty_notes) == 0
        assert "Found 11 new cards in a target collection of 16 cards" in str(event_logger)

        assert result.reorder_result_list[0].num_cards_repositioned == 11
        assert result.num_cards_repositioned == 11

        # check order
        assert_locked_order(result.reorder_result_list[0].sorted_cards_ids)
