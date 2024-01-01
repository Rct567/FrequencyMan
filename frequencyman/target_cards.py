"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from typing import Iterator, Optional, Sequence

from anki.collection import Collection
from anki.cards import CardId, Card
from anki.notes import Note, NoteId
from anki.models import NotetypeId, NotetypeDict


class TargetCards:

    col: Collection

    all_cards_ids: Sequence[CardId]

    cards_cached:dict[CardId, Card] = {}
    notes_from_cards_cached: dict[NoteId, Note] = {}

    new_cards_stored: Optional[dict[CardId, Card]]
    new_cards_ids_stored: Optional[list[CardId]]

    def __init__(self, all_cards_ids: Sequence[CardId], col: Collection) -> None:

        self.all_cards_ids = all_cards_ids
        self.col = col
        self.new_cards_stored = None
        self.new_cards_ids_stored = None

    def get_all_cards_ids(self) -> Sequence[CardId]:

        return self.all_cards_ids

    def get_card(self, card_id: CardId) -> Card:

        if card_id in self.cards_cached:
            return self.cards_cached[card_id]

        self.cards_cached[card_id] = self.col.get_card(card_id)
        return self.cards_cached[card_id]


    def get_all_cards(self) -> Iterator[Card]:

        for card_id in self.all_cards_ids:
            yield self.get_card(card_id);


    def get_new_cards(self) -> Iterator[Card]:

        if self.new_cards_stored:
            for card in self.new_cards_stored.values():
                yield card
            return

        new_cards_cached = {}
        for card in self.get_all_cards():
            if card.queue == 0:
                yield card
                new_cards_cached[card.id] = card
        self.new_cards_stored = new_cards_cached


    def get_new_cards_ids(self) -> list[CardId]:

        if not self.new_cards_ids_stored:
            self.new_cards_ids_stored = [card.id for card in self.get_new_cards()]
        return self.new_cards_ids_stored

    def get_note(self, note_id: NoteId) -> Note:

        if note_id not in self.notes_from_cards_cached:
            self.notes_from_cards_cached[note_id] = self.col.get_note(note_id)
        return self.notes_from_cards_cached[note_id]

    def get_notes(self) -> dict[NoteId, Note]:

        notes_from_all_cards: dict[NoteId, Note] = {}

        for card in self.get_all_cards():
            if card.nid not in notes_from_all_cards:
                notes_from_all_cards[card.nid] = self.get_note(card.nid)

        return notes_from_all_cards


    def get_notes_from_new_cards(self) -> dict[NoteId, Note]:

        notes_from_new_cards: dict[NoteId, Note] = {}
        for card in self.get_new_cards():
            if card.nid not in notes_from_new_cards:
                notes_from_new_cards[card.nid] = self.get_note(card.nid)

        return notes_from_new_cards

    def get_model(self, model_id: NotetypeId) -> Optional[NotetypeDict]:

        return self.col.models.get(model_id)
