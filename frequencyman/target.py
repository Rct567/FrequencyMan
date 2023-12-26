"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from typing import Optional, Sequence, TypedDict

from anki.collection import Collection, OpChanges, OpChangesWithCount
from anki.cards import CardId, Card
from anki.notes import Note, NoteId

from .lib.utilities import profile_context, var_dump, var_dump_log

from .lib.event_logger import EventLogger
from .word_frequency_list import WordFrequencyLists
from .target_corpus_data import LangKey, TargetCorpusData


class TargetCardsResult:

    col: Collection
    all_cards_ids: Sequence[CardId]
    all_cards: list[Card]
    new_cards: list[Card]
    new_cards_ids: list[CardId]
    notes_from_cards: dict[NoteId, Note]

    def __init__(self, all_cards_ids: Sequence[CardId], col: Collection) -> None:

        self.all_cards_ids = all_cards_ids
        self.all_cards = [col.get_card(card_id) for card_id in self.all_cards_ids]
        self.new_cards = [card for card in self.all_cards if card.queue == 0]
        self.new_cards_ids = [card.id for card in self.new_cards]
        self.col = col
        self.notes_from_cards = {}

    def get_notes(self) -> dict[NoteId, Note]:

        for card in self.all_cards:
            if card.nid not in self.notes_from_cards:
                self.notes_from_cards[card.nid] = self.col.get_note(card.nid)

        return self.notes_from_cards

    def get_notes_from_new_cards(self) -> dict[NoteId, Note]:

        notes_from_new_cards: dict[NoteId, Note] = {}
        for card in self.new_cards:
            if card.nid not in self.notes_from_cards:
                self.notes_from_cards[card.nid] = self.col.get_note(card.nid)
            notes_from_new_cards[card.nid] = self.notes_from_cards[card.nid]

        return notes_from_new_cards


class TargetReorderResult():

    success: bool
    error: Optional[str]
    num_cards_repositioned: int
    cards_repositioned: bool
    sorted_cards_ids: list[CardId]
    target_cards: Optional[TargetCardsResult]
    modified_dirty_notes: dict[NoteId, Optional[Note]]
    repositioning_anki_op_changes: Optional[OpChangesWithCount]

    def __init__(self, success: bool, error: Optional[str] = None) -> None:

        if not success and error is None:
            raise ValueError("No error given for unsuccessful result!")

        self.success = success
        self.error = error
        self.num_cards_repositioned = 0
        self.cards_repositioned = False
        self.sorted_cards_ids = []
        self.target_cards = None
        self.modified_dirty_notes = {}
        self.repositioning_anki_op_changes = None

    def with_repositioning_data(self, sorted_cards_ids: list[CardId], num_cards_repositioned: int,
                                target_cards: TargetCardsResult, repositioning_anki_op_changes: Optional[OpChangesWithCount] = None):

        self.sorted_cards_ids = sorted_cards_ids
        self.num_cards_repositioned = num_cards_repositioned
        self.cards_repositioned = num_cards_repositioned > 0
        self.target_cards = target_cards
        self.repositioning_anki_op_changes = repositioning_anki_op_changes

        return self

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(f'{k}={v}' for k, v in vars(self).items())})"


class ConfigTargetDataNote(TypedDict):
    name: str
    fields: dict[str, str]


class ConfigTargetData(TypedDict, total=False):
    deck: str
    decks: str
    scope_query: str
    reorder_scope_query: str
    notes: list[ConfigTargetDataNote]


class Target:

    config_target: ConfigTargetData
    index_num: int
    scope_query: Optional[str]
    col: Collection
    reorder_scope_query: Optional[str]

    corpus_cache: dict[tuple, TargetCorpusData] = {}
    target_cards_cache: dict[tuple, TargetCardsResult] = {}

    def __init__(self, target: ConfigTargetData, index_num: int, col: Collection) -> None:
        self.config_target = target
        self.index_num = index_num
        self.scope_query = None
        self.reorder_scope_query = None
        self.col = col

    def get_config_target_float_val(self, key: str) -> Optional[float]:
        val = self.config_target.get(key, "")
        if isinstance(val, str) and val.replace(".", "").isnumeric():
            return float(val)
        return None

    def get_notes(self) -> dict[str, dict[str, str]]:
        return {note['name']: note['fields'] for note in self.config_target.get('notes', [])}

    def __get_all_language_keys(self) -> list[LangKey]:
        keys = []
        for note in self.config_target.get('notes', []):
            for lang_key in note['fields'].values():
                keys.append(LangKey(lang_key.lower()))
        return keys

    def __get_query_defined_scope(self) -> Optional[str]:

        scope_queries: list[str] = []

        # defined deck

        target_decks: list[str] = []

        if "deck" in self.config_target:
            if isinstance(self.config_target["deck"], str) and len(self.config_target["deck"]) > 0:
                target_decks.append(self.config_target["deck"])
            elif isinstance(self.config_target["deck"], list):
                target_decks.extend([deck_name for deck_name in self.config_target["deck"] if isinstance(deck_name, str) and len(deck_name) > 0])
        if "decks" in self.config_target:
            if isinstance(self.config_target["decks"], str) and len(self.config_target["decks"]) > 1:
                target_decks.extend([deck_name.strip(" ,") for deck_name in self.config_target["decks"].split(",") if len(deck_name.strip(" ,")) > 0])
            elif isinstance(self.config_target["decks"], list):
                target_decks.extend([deck_name for deck_name in self.config_target["decks"] if isinstance(deck_name, str) and len(deck_name) > 0])

        if len(target_decks) > 0:
            for deck_name in target_decks:
                if len(deck_name) > 0:
                    scope_queries.append('"deck:' + deck_name + '"')

        # scope query

        if "scope_query" in self.config_target and isinstance(self.config_target["scope_query"], str) and len(self.config_target["scope_query"]) > 0:
            scope_queries.append(self.config_target["scope_query"])

        # result
        if len(scope_queries) > 0:
            scope_query = " OR ".join(scope_queries)
            return "("+scope_query+")"

        return ""

    def __construct_scope_query(self) -> str:
        target_notes = self.config_target.get("notes", []) if isinstance(self.config_target.get("notes"), list) else []
        note_queries = ['"note:'+note_type['name']+'"' for note_type in target_notes if isinstance(note_type['name'], str)]

        if len(note_queries) < 1:
            return ''

        search_query = "(" + " OR ".join(note_queries) + ")"

        scope_query = self.__get_query_defined_scope()

        if (scope_query is not None):
            search_query = scope_query+" AND "+search_query

        return search_query

    def __get_scope_query(self) -> str:
        if self.scope_query is None:
            self.scope_query = self.__construct_scope_query()
        return self.scope_query

    def __get_reorder_scope_query(self) -> Optional[str]:
        if self.reorder_scope_query is None:
            if isinstance(self.config_target.get("reorder_scope_query"), str) and len(self.config_target.get("reorder_scope_query", "")) > 0:
                self.reorder_scope_query = self.__construct_scope_query()+" AND ("+self.config_target.get("reorder_scope_query", "")+")"
        return self.reorder_scope_query

    def get_cards(self, search_query: Optional[str] = None, use_cache: bool = False) -> TargetCardsResult:

        if not search_query:
            search_query = self.__get_scope_query()

        cache_key = (search_query, str(self.get_notes()), self.col)

        if use_cache and cache_key in self.target_cards_cache:
            return self.target_cards_cache[cache_key]

        target_cards_ids = self.col.find_cards(search_query, order="c.due asc")
        target_cards = TargetCardsResult(target_cards_ids, self.col)
        if use_cache:
            self.target_cards_cache[cache_key] = target_cards
        return target_cards

    def __get_cached_corpus_data(self, target_cards: TargetCardsResult, word_frequency_lists: WordFrequencyLists) -> TargetCorpusData:

        cache_key = (str(target_cards.all_cards_ids), str(self.get_notes()), self.col, word_frequency_lists)
        if cache_key in self.corpus_cache:
            return self.corpus_cache[cache_key]

        target_corpus_data = TargetCorpusData()
        if familiarity_sweetspot_point := self.get_config_target_float_val('familiarity_sweetspot_point'):
            target_corpus_data.familiarity_sweetspot_point = familiarity_sweetspot_point

        target_corpus_data.create_data(target_cards.all_cards, self.get_notes(), self.col, word_frequency_lists)
        self.corpus_cache[cache_key] = target_corpus_data
        return target_corpus_data

    def reorder_cards(self, reorder_starting_from: int, word_frequency_lists: WordFrequencyLists,
                      event_logger: EventLogger, modified_dirty_notes: dict[NoteId, Optional[Note]]) -> TargetReorderResult:

        from .card_ranker import CardRanker

        if "note:" not in self.__get_scope_query():
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
            target_cards = self.get_cards(use_cache=True)

        num_new_cards = len(target_cards.new_cards_ids)

        if num_new_cards < 1:
            event_logger.add_entry("Found no new cards in a target collection of {:n} cards.".format(len(target_cards.all_cards)))
            return TargetReorderResult(success=False, error="No new cards to reorder.")
        else:
            event_logger.add_entry("Found {:n} new cards in a target collection of {:n} cards.".format(num_new_cards, len(target_cards.all_cards)))

        # Get corpus data

        with event_logger.add_benchmarked_entry("Creating corpus data from target cards."):
            target_corpus_data = self.__get_cached_corpus_data(target_cards, word_frequency_lists)

        # If reorder scope is defined, use it for reordering
        reorder_scope_query = self.__get_reorder_scope_query()
        reorder_scope_target_cards = target_cards
        if reorder_scope_query:
            new_target_cards = self.get_cards(reorder_scope_query)
            if not new_target_cards.all_cards:
                event_logger.add_entry("Reorder scope query yielded no results!")
                return TargetReorderResult(success=False, error="Reorder scope query yielded no results!")
            elif not new_target_cards.new_cards:
                event_logger.add_entry("Reorder scope query yielded no new cards to reorder!")
                return TargetReorderResult(success=True)
            elif new_target_cards.all_cards_ids == target_cards.all_cards_ids:
                event_logger.add_entry("Reorder scope had no effect (same result as main scope of target)!")
            else:
                reorder_scope_target_cards = new_target_cards
                num_new_cards_main_scope = len(target_cards.new_cards)
                num_new_card_reorder_scope = len(new_target_cards.new_cards)
                if num_new_card_reorder_scope < num_new_cards_main_scope:
                    event_logger.add_entry("Reorder scope query reduced new cards in target from {:n} to {:n}.".format(num_new_cards_main_scope, num_new_card_reorder_scope))
                else:
                    event_logger.add_entry("Using reorder scope query, but it did not reduce the amount of new cards in target.")

        # Sort cards
        with event_logger.add_benchmarked_entry("Ranking cards and creating a new sorted list."):

            card_ranker = CardRanker(target_corpus_data, word_frequency_lists, self.col, modified_dirty_notes)

            # Use any custom ranking weights defined in target definition
            for attribute in card_ranker.ranking_factors_span.keys():
                if target_setting_val := self.get_config_target_float_val('ranking_'+attribute):
                    card_ranker.ranking_factors_span[attribute] = target_setting_val

            # Calculate ranking and sort cards
            card_rankings = card_ranker.calc_cards_ranking(target_cards)
            sorted_cards = sorted(reorder_scope_target_cards.new_cards, key=lambda card: card_rankings[card.id], reverse=True)

            sorted_cards_ids = [card.id for card in sorted_cards]

        # Reposition
        repositioning_required = reorder_scope_target_cards.new_cards_ids != sorted_cards_ids
        repositioning_anki_op_changes = None
        num_cards_repositioned = 0

        if not repositioning_required:
            event_logger.add_entry("Repositioning {:n} cards not needed for this target.".format(len(sorted_cards_ids)))
        else:
            event_logger.add_entry("Repositioning {:n} cards for this target.".format(len(sorted_cards_ids)))
            self.col.sched.schedule_cards_as_new(sorted_cards_ids)
            repositioning_anki_op_changes = self.col.sched.reposition_new_cards(
                card_ids=sorted_cards_ids,
                starting_from=reorder_starting_from,
                step_size=1,
                randomize=False,
                shift_existing=True
            )
            num_cards_repositioned = len(sorted_cards_ids)

        # Result
        return TargetReorderResult(success=True).with_repositioning_data(
            sorted_cards_ids=sorted_cards_ids,
            target_cards=target_cards,
            num_cards_repositioned=num_cards_repositioned,
            repositioning_anki_op_changes=repositioning_anki_op_changes
        )
