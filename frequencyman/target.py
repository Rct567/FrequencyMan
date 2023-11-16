from dataclasses import dataclass
from typing import Optional, Sequence, Tuple, TypedDict

from anki.collection import Collection, OpChanges, OpChangesWithCount
from anki.cards import CardId, Card
from anki.notes import Note, NoteId

from .lib.utilities import var_dump, var_dump_log

from .lib.event_logger import EventLogger
from .word_frequency_list import WordFrequencyLists
from .target_corpus_data import LangKey


ConfigTargetDataNotes = TypedDict('TargetDataNotes', {'name': str, 'fields': dict[str, str]})
ConfigTargetData = TypedDict('TargetData', {'deck': str, 'notes': list[ConfigTargetDataNotes]})


@dataclass(frozen=True)
class TargetCardsResult:
    all_cards_ids: Sequence[CardId]
    all_cards: list[Card]
    new_cards: list[Card]
    new_cards_ids: Sequence[CardId]


class TargetReorderResult():

    success: bool
    sorted_cards_ids: list[CardId]
    repositioning_required: bool
    error: Optional[str]
    modified_dirty_notes: list[Note]

    def __init__(self, success: bool, sorted_cards_ids: Optional[list[CardId]] = None, repositioning_required: Optional[bool] = None,
                 error: Optional[str] = None, modified_dirty_notes: list[Note] = []) -> None:
        if (not success and error is None):
            raise ValueError("No error given for unsuccessful result!")
        self.success = success
        if sorted_cards_ids is not None:
            self.sorted_cards_ids = sorted_cards_ids
            if (repositioning_required is None):
                raise ValueError("No repositioning_required given for sorted cards!")
            else:
                self.repositioning_required = repositioning_required
        self.modified_dirty_notes = modified_dirty_notes

        self.error = error


class Target:

    target: ConfigTargetData
    index_num: int
    query: Optional[str]

    def __init__(self, target: ConfigTargetData, index_num: int) -> None:
        self.target = target
        self.index_num = index_num
        self.query = None

    def __getitem__(self, key):
        return self.target[key]

    def __contains__(self, key):
        return key in self.target

    def keys(self):
        return self.target.keys()

    def values(self):
        return self.target.values()

    def items(self):
        return self.target.items()

    def get(self, key, default=None):
        return self.target.get(key, default)

    def get_notes(self) -> dict[str, dict[str, str]]:
        return {note.get('name'): note.get('fields', {}) for note in self.target.get('notes', [])}

    def __get_all_language_keys(self) -> list[LangKey]:
        keys = []
        for note in self.target.get('notes', []):
            for lang_key in note['fields'].values():
                keys.append(LangKey(lang_key.lower()))
        return keys

    def __get_scope_search_query(self) -> Optional[str]:

        scope_queries = []

        # defined deck

        target_decks = []

        if "deck" in self:
            if isinstance(self.get("deck"), str) and len(self.get("deck")) > 0:
                target_decks.append(self.get("deck"))
            elif isinstance(self.get("deck"), list):
                target_decks.extend([deck_name for deck_name in self.get("deck", []) if isinstance(deck_name, str) and len(deck_name) > 0])
        if "decks" in self:
            if isinstance(self.get("decks"), str) and len(self.get("decks")) > 1:
                target_decks.extend([deck_name.strip(" ,") for deck_name in self.get("decks").split(",") if len(deck_name.strip(" ,")) > 0])
            elif isinstance(self.get("decks"), list):
                target_decks.extend([deck_name for deck_name in self.get("decks", []) if isinstance(deck_name, str) and len(deck_name) > 0])

        if len(target_decks) > 0:
            for deck_name in target_decks:
                if len(deck_name) > 0:
                    scope_queries.append('"deck:' + deck_name + '"')

        # scope query

        if "scope_query" in self and isinstance(self.get("scope_query"), str) and len(self.get("scope_query")) > 0:
            scope_queries.append(self.get('scope_query'))

        # result
        if len(scope_queries) > 0:
            scope_query = " OR ".join(scope_queries)
            return "("+scope_query+")"

    def __construct_search_query(self) -> str:
        target_notes = self.get("notes", []) if isinstance(self.get("notes"), list) else []
        note_queries = ['"note:'+note_type['name']+'"' for note_type in target_notes if isinstance(note_type['name'], str)]

        if len(note_queries) < 1:
            return ''

        search_query = "(" + " OR ".join(note_queries) + ")"

        scope_query = self.__get_scope_search_query()

        if (scope_query is not None):
            search_query = scope_query+" AND "+search_query

        return search_query

    def __get_search_query(self) -> str:
        if (self.query is None):
            self.query = self.__construct_search_query()
        return self.query

    def __get_cards(self, col: Collection) -> TargetCardsResult:

        all_cards_ids = col.find_cards(self.__get_search_query(), order="c.due asc")
        all_cards = [col.get_card(card_id) for card_id in all_cards_ids]
        new_cards = [card for card in all_cards if card.queue == 0]
        new_cards_ids: Sequence[CardId] = [card.id for card in new_cards]
        return TargetCardsResult(all_cards_ids, all_cards, new_cards, new_cards_ids)

    def reorder_cards(self, word_frequency_lists: WordFrequencyLists, col: Collection, event_logger: EventLogger) -> TargetReorderResult:

        from .card_ranker import CardRanker
        from .target_corpus_data import TargetCorpusData

        if "note:" not in self.__get_search_query():
            error_msg = "No valid note type defined. At least one note is required for reordering!"
            event_logger.add_entry(error_msg)
            return TargetReorderResult(success=False, error=error_msg)

        # Check defined target lang keys and then load frequency lists for target
        for lang_key in self.__get_all_language_keys():
            if not word_frequency_lists.key_has_frequency_list_file(lang_key):
                error_msg = "No word frequency list file found for key '{}'!".format(lang_key)
                event_logger.add_entry(error_msg)
                return TargetReorderResult(success=False, error=error_msg)

        with event_logger.add_benchmarked_entry("Loading word frequency lists."):
            word_frequency_lists.load_frequency_lists(self.__get_all_language_keys())

        # Get cards for target
        with event_logger.add_benchmarked_entry("Gathering cards from target collection."):
            target_cards = self.__get_cards(col)

        event_logger.add_entry("Found {:n} new cards in a target collection of {:n} cards.".format(len(target_cards.new_cards_ids), len(target_cards.all_cards)))

        # Get corpus data
        target_corpus_data = TargetCorpusData(word_frequency_lists)
        with event_logger.add_benchmarked_entry("Creating corpus data from target cards."):
            target_corpus_data.create_data(target_cards.all_cards, self, col)

        # Sort cards
        with event_logger.add_benchmarked_entry("Ranking cards and creating a new sorted list."):
            card_ranker = CardRanker(target_corpus_data, word_frequency_lists, col)
            card_rankings = card_ranker.calc_cards_ranking(target_cards.new_cards)
            sorted_cards = sorted(target_cards.new_cards, key=lambda card: card_rankings[card.id], reverse=True)
            sorted_cards_ids = [card.id for card in sorted_cards]

        repositioning_required = target_cards.new_cards_ids != sorted_cards_ids

        return TargetReorderResult(success=True, sorted_cards_ids=sorted_cards_ids,
                                   repositioning_required=repositioning_required, modified_dirty_notes=card_ranker.modified_dirty_notes)
