from typing import Callable

from anki.cards import CardId
from anki.notes import NoteId

from frequencyman.target_cards import TargetCard
from frequencyman.target_corpus_data import TargetCorpusData
from frequencyman.target_list import TargetList
from frequencyman.text_processing import WordToken

from .tools import MockCollection, MockCollectionFixture, test_collection, with_test_collection
col: MockCollectionFixture = test_collection


def card_familiarity_score(card: TargetCard):
    cards = [card]
    cards_familiarity_score_fn:  Callable[[list[TargetCard]], dict[CardId, float]]
    cards_familiarity_score_fn = TargetCorpusData._TargetCorpusData__get_cards_familiarity_score # type: ignore
    cards_scores = cards_familiarity_score_fn(cards)
    return cards_scores[card.id]


def create_card(interval_days: int, ease_factor: int, reps: int) -> TargetCard:
    return TargetCard(id=CardId(0), nid=NoteId(0), type=0, queue=0, ivl=interval_days, reps=reps, ease_factor=ease_factor, due=0, is_leech=False, is_suspended=False)


class TestTargetCorpusData:

    def test_cards_familiarity_score(self):

        # test mature cards

        mature_scored_cards: list[TargetCard] = [
            create_card(700, 2000, 20),
            create_card(320, 2200, 12),
            create_card(300, 2500, 12), # base
            create_card(280, 2600, 14),
            create_card(270, 3200, 14),
        ]

        for index, card in enumerate(mature_scored_cards):
            assert card_familiarity_score(card) >= 1.0, index

        # test immature cards

        immature_scored_cards: list[TargetCard] = [
            create_card(310, 1950, 14),
            create_card(300, 2400, 12),
            create_card(290, 2500, 50),
            create_card(260, 3500, 100),
            create_card(195, 2300, 25),
        ]

        for index, card in enumerate(immature_scored_cards):
            assert card_familiarity_score(card) < 1.0, index

        # test scores

        cards_scores_expectations: dict[TargetCard, tuple[float, int]] = {
            create_card(0, 2500, 0): (0.0, 10),
            create_card(0, 2500, 1): (0.0, 10),
            create_card(1, 2500, 0): (0.0, 10),
            create_card(300, 2500, 12): (1.0, 10),
            create_card(150, 2500, 10): (0.6, 1),
            create_card(125, 2700, 10): (0.6, 1),
            create_card(100, 3300, 10): (0.5, 1),
            create_card(105, 1800, 20): (0.4, 1),
            create_card(365*100, 4000, 500): (2.3, 1),
        }

        for index, (card, expected_score) in enumerate(cards_scores_expectations.items()):
            card_score = round(card_familiarity_score(card), expected_score[1])
            assert card_score == round(expected_score[0], expected_score[1]), index

    @with_test_collection("empty_collection")
    def test_internal_word_frequency(self, col: MockCollection):

        # Set up deck and note type
        did = col.decks.id("Default")
        model = col.models.by_name("Basic")
        assert did and model

        # Create first note with "apple banana apple"
        note1 = col.new_note(model)
        note1["Front"] = "apple banana apple"
        note1["Back"] = "test"
        col.add_note(note1, did)

        # Create second note with "banana cherry"
        note2 = col.new_note(model)
        note2["Front"] = "banana cherry"
        note2["Back"] = "test"
        col.add_note(note2, did)

        target_list = TargetList(col.lang_data, col.cacher, col)

        target_list.set_targets([
            {
                'deck': 'Default',
                'notes': [{
                    "name": "Basic",
                    "fields": {
                        "Front": "EN"
                    },
                }]
            }
        ])

        target = target_list[0]

        corpus_data = target.get_corpus_data_non_cached(target.get_cards())
        assert corpus_data
        assert corpus_data.content_metrics
        content_metrics = next(iter(corpus_data.content_metrics.values()))
        internal_wf = content_metrics.internal_word_frequency

        # Expected order: words with count=2 should come before word with count=1
        # Since apple and banana both have count=2, either order is acceptable
        expected_order_1 = [WordToken("apple"), WordToken("banana"), WordToken("cherry")]
        expected_order_2 = [WordToken("banana"), WordToken("apple"), WordToken("cherry")]

        # Assert one of the valid orders
        assert list(internal_wf.keys()) in [expected_order_1, expected_order_2]
