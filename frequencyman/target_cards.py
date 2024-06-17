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

from .lib.utilities import var_dump, var_dump_log


@dataclass
class TargetCard:
    id: CardId
    nid: NoteId
    type: int
    queue: int
    ivl: int
    reps: int
    factor: int
    is_leech: bool


class TargetCards:

    col: Collection

    all_cards_ids: Sequence[CardId]
    all_cards: Sequence[TargetCard]
    new_cards: Sequence[TargetCard]
    new_cards_ids: Sequence[CardId]
    reviewed_cards: Sequence[TargetCard]

    all_cards_notes_ids: Sequence[NoteId]
    new_cards_notes_ids: Sequence[NoteId]

    notes_from_cards_cached: dict[NoteId, Note] = {}
    leech_card_ids_cached: set[CardId] = set()
    cache_lock: Optional[Collection] = None

    def __init__(self, all_cards_ids: Sequence[CardId], col: Collection) -> None:

        self.all_cards_ids = all_cards_ids
        self.col = col

        if not TargetCards.cache_lock or TargetCards.cache_lock != col:
            TargetCards.cache_lock = col
            TargetCards.notes_from_cards_cached.clear()
            TargetCards.leech_card_ids_cached.clear()

        self.get_cards_from_db()

    def get_leech_cards_ids(self) -> set[CardId]:

        if len(self.leech_card_ids_cached) == 0:
            self.leech_card_ids_cached.update(self.col.find_cards('tag:leech'))

        return self.leech_card_ids_cached

    def get_cards_from_db(self) -> None:

        if not self.col.db:
            raise Exception("No database connection found when trying to get cards from database!")

        card_ids_str = ",".join(map(str, self.all_cards_ids))
        cards = self.col.db.execute("SELECT id, nid, type, queue, ivl, reps, factor FROM cards WHERE id IN ({}) ORDER BY due ASC".format(card_ids_str))

        all_cards: list[TargetCard] = []
        new_cards: list[TargetCard] = []
        new_cards_ids: list[CardId] = []
        reviewed_cards: list[TargetCard] = []
        all_cards_notes_ids: list[NoteId] = []
        new_cards_notes_ids: list[NoteId] = []
        leech_cards_ids = self.get_leech_cards_ids()

        for card_row in cards:
            card = TargetCard(*card_row, is_leech=False)
            card.is_leech = card.id in leech_cards_ids
            all_cards.append(card)
            all_cards_notes_ids.append(card.nid)
            if card.queue == 0:
                new_cards.append(card)
                new_cards_ids.append(card.id)
                new_cards_notes_ids.append(card.nid)
            if card.queue != 0 and card.type == 2:
                reviewed_cards.append(card)

        self.all_cards = all_cards
        self.new_cards = new_cards
        self.new_cards_ids = new_cards_ids
        self.reviewed_cards = reviewed_cards
        self.all_cards_notes_ids = sorted(set(all_cards_notes_ids))
        self.new_cards_notes_ids = sorted(set(new_cards_notes_ids))

        if len(self.all_cards_ids) != len(self.all_cards):
            raise Exception("Could not get cards from database!")

    def get_note(self, note_id: NoteId) -> Note:

        if note_id not in self.notes_from_cards_cached:
            self.notes_from_cards_cached[note_id] = self.col.get_note(note_id)

        return self.notes_from_cards_cached[note_id]

    def get_notes_from_all_cards(self) -> dict[NoteId, Note]:

        notes_from_all_cards: dict[NoteId, Note] = {}

        for card in self.all_cards:
            if card.nid not in notes_from_all_cards:
                notes_from_all_cards[card.nid] = self.get_note(card.nid)

        notes_from_all_cards = {k: v for k, v in sorted(notes_from_all_cards.items(), key=lambda item: item[0])}

        assert self.all_cards_notes_ids == list(notes_from_all_cards.keys())

        return notes_from_all_cards

    def get_notes_from_new_cards(self) -> dict[NoteId, Note]:

        notes_from_new_cards: dict[NoteId, Note] = {}
        for card in self.new_cards:
            if card.nid not in notes_from_new_cards:
                notes_from_new_cards[card.nid] = self.get_note(card.nid)

        notes_from_new_cards = {k: v for k, v in sorted(notes_from_new_cards.items(), key=lambda item: item[0])}

        assert self.new_cards_notes_ids == list(notes_from_new_cards.keys())

        return notes_from_new_cards

    def get_model(self, model_id: NotetypeId) -> Optional[NotetypeDict]:

        return self.col.models.get(model_id)

    def __len__(self) -> int:

        return len(self.all_cards_ids)
