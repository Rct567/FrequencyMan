"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from typing import Optional, Sequence

from anki.collection import Collection
from anki.cards import CardId, Card
from anki.notes import Note, NoteId
from anki.models import NotetypeId, NotetypeDict

from .lib.utilities import profile_context, var_dump, var_dump_log


class TargetCards:

    col: Collection
    all_cards_ids: Sequence[CardId]
    all_cards: list[Card]
    new_cards: list[Card]
    new_cards_ids: list[CardId]
    notes_from_cards_cached: dict[NoteId, Note] = {}

    def __init__(self, all_cards_ids: Sequence[CardId], col: Collection) -> None:

        self.all_cards_ids = all_cards_ids
        self.all_cards = [col.get_card(card_id) for card_id in self.all_cards_ids]
        self.new_cards = [card for card in self.all_cards if card.queue == 0]
        self.new_cards_ids = [card.id for card in self.new_cards]
        self.col = col

    def get_note(self, note_id: NoteId) -> Note:

        if note_id not in self.notes_from_cards_cached:
            self.notes_from_cards_cached[note_id] = self.col.get_note(note_id)
        return self.notes_from_cards_cached[note_id]

    def get_notes(self) -> dict[NoteId, Note]:

        for card in self.all_cards:
            self.get_note(card.nid)

        return self.notes_from_cards_cached

    def get_notes_from_new_cards(self) -> dict[NoteId, Note]:

        notes_from_new_cards: dict[NoteId, Note] = {}
        for card in self.new_cards:
            notes_from_new_cards[card.nid] = self.get_note(card.nid)

        return notes_from_new_cards

    def get_model(self, model_id: NotetypeId) -> Optional[NotetypeDict]:

        return self.col.models.get(model_id)
