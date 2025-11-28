
from frequencyman.target_cards import TargetCards

from tests.tools import (
    MockCollection,
    with_test_collection,
    test_collection as test_collection_fixture
)

col = test_collection_fixture

class TestTargetCards:

    @with_test_collection("big_collection_es")
    def test_days_overdue_cards(self, col: MockCollection):

        # this test checks if days_overdue matches with Anki's due calculations.
        # note: manually test this by changing the system time (before+after rollover hour).
        # changing the time in Python alone is not enough to make it work properly.

        assert col.conf['rollover'] == 7
        due_cards_ids_from_find_cards = col.find_cards('is:due')
        overdue_cards_ids_from_find_cards = col.find_cards('is:due -prop:due=0')

        target_cards = TargetCards(col.find_cards('*'), col)

        # note: days_overdue is set on all reviewed cards, including suspended ones,
        # but for Anki, suspended cards are not due.

        due_cards_ids_from_target_cards = [card.id for card in target_cards.all_cards if card.days_overdue is not None and not card.is_suspended]
        overdue_cards_ids_from_target_cards = [card.id for card in target_cards.all_cards if card.days_overdue is not None and card.days_overdue > 0 and not card.is_suspended]

        assert sorted(due_cards_ids_from_find_cards) == sorted(due_cards_ids_from_target_cards)
        assert sorted(overdue_cards_ids_from_find_cards) == sorted(overdue_cards_ids_from_target_cards)
