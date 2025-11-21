"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from datetime import datetime
from typing import Callable, ClassVar, Optional
from collections.abc import Sequence

from anki.collection import Collection
from anki.cards import CardId
from anki.notes import Note, NoteId
from anki.models import NotetypeId, NotetypeDict
from anki.utils import int_time

from .lib.utilities import dataclass_with_slots


@dataclass_with_slots(frozen=True)
class TargetCard:
    id: CardId
    nid: NoteId
    type: int
    queue: int
    ivl: int
    reps: int
    ease_factor: int
    due: int
    is_leech: bool
    is_suspended: bool
    days_overdue: Optional[int] = None

    @staticmethod
    def get_days_overdue(col: Collection) -> Callable[[int, int, int], Optional[int]]:

        collection_time = col.crt
        rollover = col.conf['rollover']
        rollover_seconds = 60 * 60 * (rollover - 1)

        now = int_time()
        if datetime.fromtimestamp(now).hour < rollover:
            now -= rollover_seconds # adjust for 'next day starts at'

        def _from_card(card_queue: int, card_type: int, card_due: int) -> Optional[int]:
            assert -3 <= card_queue < 5
            assert 0 < card_type < 4

            is_review = card_queue != 0 and card_type == 2
            if not is_review:
                return None

            due_date = collection_time + (card_due * 86400)
            is_due = due_date < now

            if not is_due:
                return None

            days_overdue = (now - due_date) // 86400
            return days_overdue  # if days_overdue is 0 then its also just due

        return _from_card


class TargetCards:

    col: Collection

    all_cards_ids: Sequence[CardId]
    all_cards: Sequence[TargetCard]
    new_cards: Sequence[TargetCard]
    new_cards_ids: Sequence[CardId]
    reviewed_cards: Sequence[TargetCard]

    notes_ids_all_cards: Sequence[NoteId]
    notes_ids_new_cards_set: set[NoteId]
    notes_ids_new_cards: Sequence[NoteId]

    notes_from_cards_cached: ClassVar[dict[NoteId, Note]] = {}
    leech_card_ids_cached: ClassVar[set[CardId]] = set()
    cache_lock: Optional[Collection] = None

    def __init__(self, all_cards_ids: Sequence[CardId], col: Collection) -> None:

        self.all_cards_ids = all_cards_ids
        self.col = col

        if not TargetCards.cache_lock or TargetCards.cache_lock != col:
            TargetCards.cache_lock = col
            TargetCards.notes_from_cards_cached.clear()
            TargetCards.leech_card_ids_cached.clear()

        self.__get_cards_from_db()

    def __get_leech_cards_ids(self) -> set[CardId]:

        if len(self.leech_card_ids_cached) == 0:
            self.leech_card_ids_cached.update(self.col.find_cards('tag:leech'))

        return self.leech_card_ids_cached

    def __get_cards_from_db(self) -> None:

        if not self.col.db:
            raise Exception("No database connection found when trying to get cards from database!")

        card_ids_str = ",".join(map(str, self.all_cards_ids))
        cards = self.col.db.execute("SELECT id, nid, type, queue, ivl, reps, factor, due FROM cards WHERE id IN ({}) ORDER BY due ASC".format(card_ids_str))

        all_cards: list[TargetCard] = []
        new_cards: list[TargetCard] = []
        new_cards_ids: list[CardId] = []
        reviewed_cards: list[TargetCard] = []
        notes_ids_all_cards: set[NoteId] = set()
        notes_ids_new_cards: set[NoteId] = set()
        leech_cards_ids = self.__get_leech_cards_ids()
        get_days_overdue = TargetCard.get_days_overdue(self.col)

        for card_row in cards:

            card_id, note_id, card_type, card_queue, card_ivl, card_reps, card_factor, card_due = card_row
            is_leech = card_id in leech_cards_ids
            is_suspended = card_queue == -1
            is_new = card_queue == 0
            is_reviewed = card_queue != 0 and card_type == 2
            assert not (is_new and is_reviewed)

            if is_reviewed:
                days_overdue = get_days_overdue(card_queue, card_type, card_due)
            else:
                days_overdue = None

            card = TargetCard(card_id, note_id, card_type, card_queue, card_ivl, card_reps, card_factor, card_due, is_leech, is_suspended, days_overdue)

            if is_new:
                new_cards.append(card)
                new_cards_ids.append(card.id)
                notes_ids_new_cards.add(card.nid)
            if is_reviewed:
                reviewed_cards.append(card)
            all_cards.append(card)
            notes_ids_all_cards.add(card.nid)

        self.all_cards = all_cards
        self.new_cards = new_cards
        self.new_cards_ids = new_cards_ids
        self.reviewed_cards = reviewed_cards
        self.notes_ids_all_cards = sorted(notes_ids_all_cards)
        self.notes_ids_new_cards_set = notes_ids_new_cards
        self.notes_ids_new_cards = sorted(self.notes_ids_new_cards_set)

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

        assert self.notes_ids_all_cards == list(notes_from_all_cards.keys())

        return notes_from_all_cards

    def get_notes_from_new_cards(self) -> dict[NoteId, Note]:

        notes_from_new_cards: dict[NoteId, Note] = {}
        for card in self.new_cards:
            if card.nid not in notes_from_new_cards:
                notes_from_new_cards[card.nid] = self.get_note(card.nid)

        notes_from_new_cards = {k: v for k, v in sorted(notes_from_new_cards.items(), key=lambda item: item[0])}

        assert self.notes_ids_new_cards == list(notes_from_new_cards.keys())

        return notes_from_new_cards

    def get_model(self, model_id: NotetypeId) -> Optional[NotetypeDict]:

        return self.col.models.get(model_id)

    def __len__(self) -> int:

        return len(self.all_cards_ids)
