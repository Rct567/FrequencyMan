import pytest
import os
import shutil

from frequencyman.target_list import TargetList, TargetListReorderResult
from frequencyman.lib.event_logger import EventLogger
from frequencyman.word_frequency_list import LangKey, WordFrequencyLists

from anki.collection import Collection, OpChanges, OpChangesWithCount
from aqt.operations import QueryOp, CollectionOp

from anki.cards import CardId, Card
from anki.notes import Note, NoteId


def store_card_id_list(filename: str, int_list: list[CardId]) -> None:
    with open(filename, 'w') as file:
        file.write('\n'.join(map(str, int_list)))


def read_card_id_list(filename: str) -> list[CardId]:
    with open(filename, 'r') as file:
        int_list = [CardId(int(line.strip())) for line in file]
    return int_list


class TestTargetListReorder:

    TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
    TEST_COLLECTIONS_DIR = os.path.join(TEST_DATA_DIR, 'collections')

    def get_test_collection(self, test_collection_name: str, collection_test_seq_num: int):

        collection_dir = os.path.join(self.TEST_COLLECTIONS_DIR, test_collection_name)

        word_frequency_lists = WordFrequencyLists(os.path.join(collection_dir, 'frequency_lists'))

        # create temporary collection
        collection_file = os.path.join(collection_dir, test_collection_name+".anki2")
        temp_collection_file = os.path.join(collection_dir, test_collection_name+"_"+str(collection_test_seq_num)+"_temp.anki2")
        if os.path.exists(temp_collection_file):
            os.remove(temp_collection_file)
        shutil.copy(collection_file, temp_collection_file)

        # helper function used to lock-in and assert order
        def assert_locked_order(sorted_cards_ids: list[CardId]):
            order_file = os.path.join(collection_dir, 'expected_order.txt')

            if os.path.exists(order_file):
                expected_order = read_card_id_list(order_file)
                assert sorted_cards_ids == expected_order
            else:
                store_card_id_list(order_file, sorted_cards_ids)
                print("WARNING: Order file for '{}' didn't exist yet!".format(test_collection_name))

        # return result
        return Collection(temp_collection_file), word_frequency_lists, assert_locked_order

    def test_reorder_cards_big_collection_es(self):

        col, word_frequency_lists, assert_locked_order = self.get_test_collection('big_collection_es', collection_test_seq_num=0)

        target_list = TargetList(word_frequency_lists, col)

        target_list.set_targets([
            {
                'deck': 'Spanish',
                'notes': [{
                    "name": "-- My spanish --",
                    "fields": {
                        "Meaning": "EN",
                        "Sentence": "ES"
                    },
                }]
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
        assert "Updating 5479 modified notes" in str(event_logger)

        # check value of focus words
        assert col.get_note(NoteId(1548089874907))['fm_focus_words'] == "ajedrez | chess"
        assert col.get_note(NoteId(1548089876496))['fm_focus_words'] == "fotografías, pasatiempo | hobby"
        assert col.get_note(NoteId(1671840154010))['fm_focus_words'] == "hacerlas, eficaz | efficient"

        # these had focus words set before, but should now be empty
        for note_id in {1651511407504, 1678410313201, 1692391247701, 1548089872580}:
            assert col.get_note(NoteId(note_id))['fm_focus_words'] == ""

        # some extras that were already empty
        for note_id in {1695675879863, 1695675879703, 1687208310219}:
            assert col.get_note(NoteId(note_id))['fm_focus_words'] == ""

        # these were empty before, but should now have a value
        notes_none_empty_focus_word = {1548089873399, 1548089879591, 1546160205490, 1562346819967, 1546959316161, 1562346819250, 1548089878113,
                                       1548089874025, 1651511363702, 1548089877279, 1548089878563, 1548089878527}

        for note_id in notes_none_empty_focus_word:
            assert len(col.get_note(NoteId(note_id))['fm_focus_words']) > 20

        # check order
        assert_locked_order(target_result.sorted_cards_ids)

    def test_two_deck_collection(self):

        col, word_frequency_lists, assert_locked_order = self.get_test_collection('two_deck_collection', collection_test_seq_num=0)

        target_list = TargetList(word_frequency_lists, col)

        validity_state = target_list.set_targets([
            {
                'deck': 'decka',
                'notes': [{
                    "name": "Basic",
                    "fields": {
                        "Front": "EN",
                        "Back": "EN"
                    },
                }]
            },
            {
                'deck': 'deckb',
                'notes': [{
                    "name": "Basic",
                    "fields": {
                        "Front": "EN",
                        "Back": "EN"
                    },
                }]
            }
        ])

        assert validity_state == (1, "")
        assert len(target_list) == 2

        # reorder cards
        event_logger = EventLogger()
        result = target_list.reorder_cards(col, event_logger)
        assert isinstance(result, TargetListReorderResult)
        assert len(result.reorder_result_list) == len(target_list)

        # check result
        reorder_result = result.reorder_result_list[0]
        assert reorder_result.success
        assert reorder_result.cards_repositioned
        assert reorder_result.error is None
        assert len(result.reorder_result_list[0].modified_dirty_notes) == 0
        assert len(result.reorder_result_list[1].modified_dirty_notes) == 0
        assert "Reordering target #0" in str(event_logger)
        assert "Found 7 new cards in a target collection of 10 cards" in str(event_logger)
        assert "Reordering target #1" in str(event_logger)
        assert "Found 4 new cards in a target collection of 6 cards" in str(event_logger)

        # check order
        assert_locked_order(result.reorder_result_list[0].sorted_cards_ids+result.reorder_result_list[1].sorted_cards_ids)
