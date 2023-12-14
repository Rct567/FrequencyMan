from dataclasses import dataclass
from typing import Optional, Sequence, Tuple, TypedDict

from anki.collection import Collection, OpChanges, OpChangesWithCount
from anki.cards import CardId, Card
from anki.notes import Note, NoteId

from .lib.utilities import var_dump, var_dump_log

from .lib.event_logger import EventLogger
from .word_frequency_list import WordFrequencyLists
from .target_corpus_data import LangKey


ConfigTargetDataNotes = TypedDict('ConfigTargetDataNotes', {'name': str, 'fields': dict[str, str]})
ConfigTargetData = TypedDict('ConfigTargetData', {'deck': str, 'notes': list[ConfigTargetDataNotes]})


@dataclass(frozen=True)
class TargetCardsResult:
    all_cards_ids: Sequence[CardId]
    all_cards: list[Card]
    new_cards: list[Card]
    new_cards_ids: Sequence[CardId]


class TargetReorderResult():

    success: bool
    error: Optional[str]
    cards_repositioned: bool
    num_cards_repositioned: int
    sorted_cards_ids: list[CardId]
    modified_dirty_notes: dict[NoteId, Note]
    repositioning_anki_op_changes: Optional[OpChangesWithCount] = None

    def __init__(self, success: bool, sorted_cards_ids: Optional[list[CardId]] = None, num_cards_repositioned: Optional[int] = 0,
                 error: Optional[str] = None, modified_dirty_notes: dict[NoteId, Note] = {}, repositioning_anki_op_changes: Optional[OpChangesWithCount] = None ) -> None:

        if not success and error is None:
            raise ValueError("No error given for unsuccessful result!")

        if sorted_cards_ids is not None:
            self.sorted_cards_ids = sorted_cards_ids
            if num_cards_repositioned is None:
                raise ValueError("No num_cards_repositioned given for sorted cards!")
        else:
            self.sorted_cards_ids = []
        self.modified_dirty_notes = modified_dirty_notes

        self.num_cards_repositioned = num_cards_repositioned if num_cards_repositioned is not None else 0
        self.cards_repositioned = num_cards_repositioned > 0 if num_cards_repositioned is not None else False
        self.repositioning_anki_op_changes = repositioning_anki_op_changes
        self.success = success
        self.error = error

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(f'{k}={v}' for k, v in vars(self).items())})"


class Target:

    target: ConfigTargetData
    index_num: int
    scope_query: Optional[str]
    reorder_scope_query: Optional[str]

    def __init__(self, target: ConfigTargetData, index_num: int) -> None:
        self.target = target
        self.index_num = index_num
        self.scope_query = None
        self.reorder_scope_query = None

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

    def __get_query_defined_scope(self) -> Optional[str]:

        scope_queries = []

        # defined deck

        target_decks = []

        if "deck" in self:
            if isinstance(self.target.get("deck"), str) and len(self.target.get("deck")) > 0:
                target_decks.append(self.get("deck"))
            elif isinstance(self.target.get("deck"), list):
                target_decks.extend([deck_name for deck_name in self.target.get("deck", []) if isinstance(deck_name, str) and len(deck_name) > 0])
        if "decks" in self:
            if isinstance(self.target.get("decks"), str) and len(self.target.get("decks", "")) > 1:
                target_decks.extend([deck_name.strip(" ,") for deck_name in self.target.get("decks", "").split(",") if len(deck_name.strip(" ,")) > 0])
            elif isinstance(self.target.get("decks"), list):
                target_decks.extend([deck_name for deck_name in self.target.get("decks", []) if isinstance(deck_name, str) and len(deck_name) > 0])

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

        return ""

    def __construct_scope_query(self) -> str:
        target_notes = self.get("notes", []) if isinstance(self.get("notes"), list) else []
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
            if isinstance(self.get("reorder_scope_query"), str) and len(self.get("reorder_scope_query")) > 0:
                self.reorder_scope_query = self.__construct_scope_query()+" AND ("+self.get("reorder_scope_query")+")"
        return self.reorder_scope_query

    def get_cards(self, col: Collection, search_query: Optional[str] = None) -> TargetCardsResult:

        if not search_query:
            search_query = self.__get_scope_query()

        all_cards_ids = col.find_cards(search_query, order="c.due asc")
        all_cards = [col.get_card(card_id) for card_id in all_cards_ids]
        new_cards = [card for card in all_cards if card.queue == 0]
        new_cards_ids = [card.id for card in new_cards]
        return TargetCardsResult(all_cards_ids, all_cards, new_cards, new_cards_ids)

    def reorder_cards(self, reorder_starting_from: int, word_frequency_lists: WordFrequencyLists, col: Collection, event_logger: EventLogger) -> TargetReorderResult:

        from .card_ranker import CardRanker
        from .target_corpus_data import TargetCorpusData

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
            target_cards = self.get_cards(col)

        num_new_cards = len(target_cards.new_cards_ids)

        if num_new_cards < 1:
            event_logger.add_entry("Found no new cards in a target collection of {:n} cards.".format(num_new_cards, len(target_cards.all_cards)))
            return TargetReorderResult(success=False, error="No new cards to reorder.")
        else:
            event_logger.add_entry("Found {:n} new cards in a target collection of {:n} cards.".format(num_new_cards, len(target_cards.all_cards)))

        # Get corpus data
        target_corpus_data = TargetCorpusData()
        with event_logger.add_benchmarked_entry("Creating corpus data from target cards."):
            target_corpus_data.create_data(target_cards.all_cards, self.get_notes(), col, word_frequency_lists)

        # If reorder scope is defined, use it for reordering
        reorder_scope_query = self.__get_reorder_scope_query()
        if reorder_scope_query:
            new_target_cards = self.get_cards(col, reorder_scope_query)
            if not new_target_cards.all_cards:
                event_logger.add_entry("Reorder scope query yielded no results!")
                return TargetReorderResult(success=False, error="Reorder scope query yielded no results!")
            elif not new_target_cards.new_cards:
                event_logger.add_entry("Reorder scope query yielded no new cards to reorder!")
                return TargetReorderResult(success=True)
            elif new_target_cards.all_cards_ids == target_cards.all_cards_ids:
                event_logger.add_entry("Reorder scope had no effect (same result as main scope of target)!")
            else:
                num_cards_main_scope = len(target_cards.all_cards)
                num_card_reorder_scope = len(new_target_cards.all_cards)
                if num_card_reorder_scope < num_cards_main_scope:
                    event_logger.add_entry("Reorder scope query reduced cards in target from {:n} to {:n}.".format(num_cards_main_scope, num_card_reorder_scope))
                    target_cards = new_target_cards

        # Sort cards
        with event_logger.add_benchmarked_entry("Ranking cards and creating a new sorted list."):

            card_ranker = CardRanker(target_corpus_data, word_frequency_lists, col)

            # Use any custom ranking weights defined in target definition
            for attribute in card_ranker.ranking_factors_span.keys():
                target_setting_val = self.get('ranking_'+attribute)
                if target_setting_val is not None and str(target_setting_val).replace(".", "").isnumeric():
                    card_ranker.ranking_factors_span[attribute] = float(target_setting_val)

            # Calculate ranking and sort cards
            card_rankings = card_ranker.calc_cards_ranking(target_cards.new_cards)
            sorted_cards = sorted(target_cards.new_cards, key=lambda card: card_rankings[card.id], reverse=True)
            card_ranker.update_meta_data_for_notes_with_non_new_cards([card for card in target_cards.all_cards if card.queue != 0])  # reviewed card also need updating
            sorted_cards_ids = [card.id for card in sorted_cards]

        # Reposition
        repositioning_required = target_cards.new_cards_ids != sorted_cards_ids
        repositioning_anki_op_changes = None
        num_cards_repositioned = 0

        if not repositioning_required:
            event_logger.add_entry("Repositioning {:n} cards not needed for this target.".format(len(sorted_cards_ids)))
        else:
            event_logger.add_entry("Repositioning {:n} cards for this target.".format(len(sorted_cards_ids)))
            col.sched.schedule_cards_as_new(sorted_cards_ids)
            repositioning_anki_op_changes = col.sched.reposition_new_cards(
                card_ids=sorted_cards_ids,
                starting_from=reorder_starting_from,
                step_size=1,
                randomize=False,
                shift_existing=True
            )
            num_cards_repositioned = len(sorted_cards_ids)

        # Result
        return TargetReorderResult(
            success=True,
            sorted_cards_ids=sorted_cards_ids,
            num_cards_repositioned=num_cards_repositioned,
            repositioning_anki_op_changes=repositioning_anki_op_changes,
            modified_dirty_notes=card_ranker.modified_dirty_notes
        )
