"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from dataclasses import dataclass
from typing import Optional, Sequence

from anki.collection import Collection
from anki.cards import CardId, Card
from anki.notes import Note, NoteId
from anki.models import NotetypeId, NotetypeDict


@dataclass
class TargetCard:
    id: CardId
    nid: NoteId
    type: int
    queue: int
    ivl: int
    reps: int
    factor: int


class TargetCards:

    col: Collection

    all_cards_ids: Sequence[CardId]
    all_cards: list[TargetCard]
    new_cards: list[TargetCard]
    new_cards_ids: list[CardId]
    reviewed_cards: list[TargetCard]

    notes_from_cards_cached: dict[NoteId, Note] = {}
    cache_lock: Optional[Collection] = None

    def __init__(self, all_cards_ids: Sequence[CardId], col: Collection) -> None:

        self.all_cards_ids = all_cards_ids
        self.col = col

        self.all_cards = []
        self.new_cards = []
        self.new_cards_ids = []
        self.reviewed_cards = []

        self.get_cards_from_db()

        if not TargetCards.cache_lock or TargetCards.cache_lock != col:
            TargetCards.cache_lock = col
            TargetCards.notes_from_cards_cached = {}

    def get_cards_from_db(self) -> None:

        if not self.col.db:
            raise Exception("No database connection found when trying to get cards from database!")

        card_ids_str = ",".join(map(str, self.all_cards_ids))
        cards = self.col.db.execute("SELECT id, nid, type, queue, ivl, reps, factor FROM cards WHERE id IN ({}) ORDER BY due ASC".format(card_ids_str))

        for card_row in cards:
            card = TargetCard(*card_row)
            self.all_cards.append(card)
            if card.queue == 0:
                self.new_cards.append(card)
                self.new_cards_ids.append(CardId(card.id))
            if card.queue != 0 and card.type == 2:
                self.reviewed_cards.append(card)

        if len(self.all_cards_ids) != len(self.all_cards):
            raise Exception("Could not get cards from database!")


    def get_note(self, note_id) -> Note:

        if note_id not in self.notes_from_cards_cached:
            self.notes_from_cards_cached[note_id] = self.col.get_note(note_id)

        return self.notes_from_cards_cached[note_id]

    def get_notes(self) -> dict[NoteId, Note]:

        notes_from_all_cards: dict[NoteId, Note] = {}

        for card in self.all_cards:
            if card.nid not in notes_from_all_cards:
                notes_from_all_cards[card.nid] = self.get_note(card.nid)

        return notes_from_all_cards

    def get_notes_from_new_cards(self) -> dict[NoteId, Note]:

        notes_from_new_cards: dict[NoteId, Note] = {}
        for card in self.new_cards:
            if card.nid not in notes_from_new_cards:
                notes_from_new_cards[card.nid] = self.get_note(card.nid)

        return notes_from_new_cards

    def get_model(self, model_id: NotetypeId) -> Optional[NotetypeDict]:

        return self.col.models.get(model_id)

    def __len__(self):

        return len(self.all_cards_ids)
