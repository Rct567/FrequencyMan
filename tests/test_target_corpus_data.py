from ast import Tuple
from math import exp
from typing import Callable
import pytest

from anki.cards import CardId, Card
from anki.notes import Note, NoteId

from frequencyman.target_cards import TargetCards, TargetCard
from frequencyman.target_corpus_data import TargetCorpusData


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

