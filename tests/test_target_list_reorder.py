import pytest
import os
import shutil

from frequencyman.target_list import TargetList, TargetListReorderResult
from frequencyman.lib.event_logger import EventLogger
from frequencyman.word_frequency_list import LangKey, WordFrequencyLists

from anki.collection import Collection, OpChanges, OpChangesWithCount
from aqt.operations import QueryOp, CollectionOp

from anki.cards import CardId

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

    def get_test_collection(self, test_collection_name: str, collection_test_seq_num:int):

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

        target_list = TargetList(word_frequency_lists)

        target_list.set_targets([
            {
                'deck': 'Spanish',
                'notes': [{
                    "fields": {
                        "Meaning": "EN",
                        "Sentence": "ES"
                    },
                    "name": "-- My spanish --"
                }]
            }
        ])

        assert len(target_list) == 1
        pre_sort_cards = target_list[0].get_cards(col)
        event_logger = EventLogger()

        # reorder cards
        result = target_list.reorder_cards(col, event_logger)

        assert isinstance(result, TargetListReorderResult)
        assert len(result.reorder_result_list) == len(target_list)

        # check result

        reorder_result = result.reorder_result_list[0]
        assert reorder_result.success
        assert reorder_result.repositioning_required
        assert reorder_result.error is None
        assert len(reorder_result.sorted_cards_ids) == len(pre_sort_cards.new_cards_ids)
        assert reorder_result.sorted_cards_ids != pre_sort_cards.new_cards_ids
        assert reorder_result.sorted_cards_ids == target_list[0].get_cards(col).new_cards_ids
        assert len(reorder_result.modified_dirty_notes) == 7883
        assert "Found 6566 new cards in a target collection of 15790 cards" in str(event_logger)
        assert "Reposition cards from targets" in str(event_logger)

        # check order
        assert_locked_order(reorder_result.sorted_cards_ids)


