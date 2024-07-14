from frequencyman.target_cards import TargetCards

from tests.tools import TestCollections


class TestTargetCards:

    def test_overdue_cards_from_db(self):

        col = TestCollections.get_test_collection('big_collection_es')
        due_cards_ids_from_find_cards = col.find_cards('is:due')
        overdue_cards_ids_from_find_cards = col.find_cards('is:due -prop:due=0')

        target_cards = TargetCards(col.find_cards('*'), col)
        due_cards_ids_from_target_cards = [card.id for card in target_cards.all_cards if card.days_overdue is not None]
        overdue_cards_ids_from_target_cards = [card.id for card in target_cards.all_cards if card.days_overdue is not None and card.days_overdue > 0]

        assert sorted(due_cards_ids_from_find_cards) == sorted(due_cards_ids_from_target_cards)
        assert sorted(overdue_cards_ids_from_find_cards) == sorted(overdue_cards_ids_from_target_cards)
