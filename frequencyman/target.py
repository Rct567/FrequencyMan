"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

import re
from typing import Any, Optional, Tuple, TypedDict, Union

from anki.collection import Collection, OpChanges, OpChangesWithCount
from anki.cards import CardId, Card
from anki.notes import Note, NoteId

from .text_processing import TextProcessing
from .lib.utilities import get_float, profile_context, var_dump_log
from .lib.event_logger import EventLogger
from .language_data import LanguageData, LangDataId
from .target_corpus_data import CorpusSegmentationStrategy, TargetCorpusData
from .target_cards import TargetCards


class TargetReorderResult():

    success: bool
    error: Optional[str]
    num_cards_repositioned: int
    cards_repositioned: bool
    sorted_cards_ids: list[CardId]
    target_cards: Optional[TargetCards]
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
        self.repositioning_anki_op_changes = None

    def with_repositioning_data(self, sorted_cards_ids: list[CardId], num_cards_repositioned: int,
                                target_cards: TargetCards, repositioning_anki_op_changes: OpChangesWithCount) -> 'TargetReorderResult':

        self.sorted_cards_ids = sorted_cards_ids
        self.num_cards_repositioned = num_cards_repositioned
        self.cards_repositioned = num_cards_repositioned > 0
        self.target_cards = target_cards
        self.repositioning_anki_op_changes = repositioning_anki_op_changes

        return self

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(f'{k}={v}' for k, v in vars(self).items())})"




class ConfiguredTargetNote(TypedDict):
    name: str
    fields: dict[str, str]


class ValidConfiguredTargetBase(TypedDict, total=False):
    deck: Optional[str]
    decks: Optional[Union[str, list[str]]]
    scope_query: Optional[str]
    reorder_scope_query: Optional[str]
    familiarity_sweetspot_point: Optional[Union[float, str]]
    suspended_card_value: Optional[float]
    suspended_leech_card_value: Optional[float]
    ideal_word_count: Optional[list[int]]
    ranking_factors: Optional[dict[str, float]]
    corpus_segmentation_strategy: Optional[str]

class ValidConfiguredTarget(ValidConfiguredTargetBase):
    notes: list[ConfiguredTargetNote]

class ReorderCacheData(TypedDict):
    target_cards: dict[Tuple, TargetCards]
    corpus: dict[Tuple, TargetCorpusData]


class Target:

    config_target: ValidConfiguredTarget
    index_num: int
    col: Collection

    main_scope_query: Optional[str]
    reorder_scope_query: Optional[str]
    target_corpus_data: Optional[TargetCorpusData]

    cache_data: Optional[ReorderCacheData]

    def __init__(self, target: ValidConfiguredTarget, index_num: int, col: Collection) -> None:

        self.config_target = target
        self.index_num = index_num
        self.main_scope_query = None
        self.reorder_scope_query = None
        self.target_corpus_data = None
        self.col = col

    @staticmethod
    def get_config_fields_per_note_type(config_target: ValidConfiguredTarget) -> dict[str, dict[str, LangDataId]]:

        config_notes = {}

        for note in config_target['notes']:
            note_fields = {field_name: LangDataId(lang_data_id.lower()) for field_name, lang_data_id in note['fields'].items()}
            config_notes[note['name']] = note_fields

        return config_notes

    @staticmethod
    def get_language_data_ids_from_config_target(config_target: ValidConfiguredTarget) -> set[LangDataId]:

        keys = set()
        for note in config_target['notes']:
            for lang_data_id in note['fields'].values():
                keys.add(LangDataId(lang_data_id.lower()))
        return keys

    @staticmethod
    def get_deck_names_from_config_target(defined_deck: Any, defined_decks: Any) -> list[str]:

        decks: list[str] = []

        if defined_deck is not None and isinstance(defined_deck, str) and len(defined_deck) > 0:
            decks.append(defined_deck)

        if defined_decks is not None and isinstance(defined_decks, list) and len(defined_decks) > 0:
            decks.extend([deck_name for deck_name in defined_decks if isinstance(deck_name, str) and len(deck_name) > 0])
        if defined_decks is not None and isinstance(defined_decks, str) and len(defined_decks) > 0:
            decks.extend([deck_name.replace('\\,', ',').strip() for deck_name in re.split(r'(?<!\\),', defined_decks) if isinstance(deck_name, str)])

        return decks

    @staticmethod
    def get_query_from_defined_main_scope(defined_deck: Optional[Any], defined_decks: Optional[Any], scope_query: Optional[Any]) -> Optional[str]:

        scope_queries: list[str] = []

        # defined decks

        decks = Target.get_deck_names_from_config_target(defined_deck, defined_decks)

        for deck_name in decks:
            if len(deck_name.strip()) > 0:
                scope_queries.append('"deck:' + deck_name + '"')

        # defined scope query

        if scope_query is not None and isinstance(scope_query, str) and len(scope_query.strip()) > 0:
            scope_queries.append(scope_query)

        # result
        if len(scope_queries) > 0:
            scope_query_result = " OR ".join(scope_queries)
            return "("+scope_query_result+")"

        return None

    @staticmethod
    def construct_main_scope_query(config_target: ValidConfiguredTarget) -> str:

        target_notes = config_target["notes"] if isinstance(config_target["notes"], list) else []
        note_queries = ['"note:'+note_type['name']+'"' for note_type in target_notes if isinstance(note_type['name'], str)]

        if len(note_queries) < 1:
            return ''

        notes_query = "(" + " OR ".join(note_queries) + ")"

        defined_scope_query = Target.get_query_from_defined_main_scope(config_target.get('deck'), config_target.get('decks'), config_target.get('scope_query'))

        if defined_scope_query is None:
            return notes_query  # main scope is just the notes

        return defined_scope_query+" AND "+notes_query

    def __get_main_scope_query(self) -> str:

        if self.main_scope_query is None:
            self.main_scope_query = self.construct_main_scope_query(self.config_target)
        return self.main_scope_query

    def __get_reorder_scope_query(self) -> Optional[str]:

        if self.reorder_scope_query is None:
            if 'reorder_scope_query' in self.config_target and self.config_target['reorder_scope_query'] is not None and len(self.config_target['reorder_scope_query']) > 0:
                self.reorder_scope_query = self.construct_main_scope_query(self.config_target)+" AND ("+self.config_target['reorder_scope_query']+")"
        return self.reorder_scope_query

    def get_cards(self, search_query: Optional[str] = None) -> TargetCards:

        if not search_query:
            search_query = self.__get_main_scope_query()

        target_cards_ids = self.col.find_cards(search_query, order="c.due asc")
        target_cards = TargetCards(target_cards_ids, self.col)

        return target_cards

    def __get_cards_cached(self, search_query: Optional[str] = None) -> TargetCards:

        if not search_query:
            search_query = self.__get_main_scope_query()

        cache_key = (search_query, self.col)

        if self.cache_data and cache_key in self.cache_data['target_cards']:
            return self.cache_data['target_cards'][cache_key]

        target_cards = self.get_cards(search_query)

        if self.cache_data:
            self.cache_data['target_cards'][cache_key] = target_cards

        return target_cards

    def get_corpus_data(self, target_cards: TargetCards, language_data: LanguageData) -> TargetCorpusData:

        if not self.target_corpus_data is None:
            return self.target_corpus_data

        self.target_corpus_data = TargetCorpusData()

        # familiarity_sweetspot_point
        configured_familiarity_sweetspot_point = self.config_target.get('familiarity_sweetspot_point')
        if isinstance(configured_familiarity_sweetspot_point, str) and configured_familiarity_sweetspot_point[0] in ['~', '^']:
            self.target_corpus_data.familiarity_sweetspot_point = configured_familiarity_sweetspot_point
        elif (familiarity_sweetspot_point := get_float(configured_familiarity_sweetspot_point)) is not None:
            self.target_corpus_data.familiarity_sweetspot_point = familiarity_sweetspot_point

        # focus_words_max_familiarity
        if (focus_words_max_familiarity := get_float(self.config_target.get('focus_words_max_familiarity'))) is not None:
            self.target_corpus_data.focus_words_max_familiarity = focus_words_max_familiarity

        # suspended_card_value
        if (suspended_card_value := get_float(self.config_target.get('suspended_card_value'))) is not None:
            self.target_corpus_data.suspended_card_value = suspended_card_value

        # suspended_leech_card_value
        if (suspended_leech_card_value := get_float(self.config_target.get('suspended_leech_card_value'))) is not None:
            self.target_corpus_data.suspended_leech_card_value = suspended_leech_card_value

        # corpus_segmentation_strategy
        if 'corpus_segmentation_strategy' in self.config_target and not self.config_target['corpus_segmentation_strategy'] is None:
            corpus_segmentation_strategy = self.config_target['corpus_segmentation_strategy'].lower()
            if corpus_segmentation_strategy == 'by_lang_data_id':
                self.target_corpus_data.segmentation_strategy = CorpusSegmentationStrategy.BY_LANG_DATA_ID
            elif corpus_segmentation_strategy == 'by_note_model_id_and_field_name':
                self.target_corpus_data.segmentation_strategy = CorpusSegmentationStrategy.BY_NOTE_MODEL_ID_AND_FIELD_NAME

        # create corpus data
        self.target_corpus_data.create_data(target_cards, self.get_config_fields_per_note_type(self.config_target), language_data)

        # done
        return self.target_corpus_data

    def __get_corpus_data_cached(self, target_cards: TargetCards, language_data: LanguageData) -> TargetCorpusData:

        cache_key = (str(target_cards.all_cards_ids), str(self.get_config_fields_per_note_type(self.config_target)), self.col, language_data,
                     self.config_target.get('familiarity_sweetspot_point'), self.config_target.get('suspended_card_value'),
                     self.config_target.get('suspended_leech_card_value'), self.config_target.get('corpus_segmentation_strategy'),
                     self.config_target.get('focus_words_max_familiarity'))

        if self.cache_data and cache_key in self.cache_data['corpus']:
            return self.cache_data['corpus'][cache_key]

        target_corpus_data = self.get_corpus_data(target_cards, language_data)

        if self.cache_data:
            self.cache_data['corpus'][cache_key] = target_corpus_data

        return target_corpus_data

    def reorder_cards(self, repositioning_starting_from: int, language_data: LanguageData, event_logger: EventLogger,
                      modified_dirty_notes: dict[NoteId, Optional[Note]], schedule_cards_as_new: bool) -> TargetReorderResult:

        if self.cache_data is None:
            raise ValueError("Cache data object required for reordering!")

        from .card_ranker import CardRanker

        if "note:" not in self.__get_main_scope_query():
            error_msg = "No valid note type defined. At least one note is required for reordering!"
            event_logger.add_entry(error_msg)
            return TargetReorderResult(success=False, error=error_msg)

        # Check defined target lang keys and then load frequency lists for target
        for lang_data_id in self.get_language_data_ids_from_config_target(self.config_target):
            if not language_data.id_has_directory(lang_data_id):
                error_msg = "No directory found for lang_data_id '{}' in '{}'!".format(lang_data_id, language_data.data_dir)
                event_logger.add_entry(error_msg)
                return TargetReorderResult(success=False, error=error_msg)

        with event_logger.add_benchmarked_entry("Loading word frequency lists."):
            language_data.load_data(self.get_language_data_ids_from_config_target(self.config_target))

            for lang_key in self.get_language_data_ids_from_config_target(self.config_target):
                if not language_data.word_frequency_lists.id_has_list_file(lang_key):
                    event_logger.add_entry("No word frequency list file found for language '{}'!".format(lang_key))

        # Get cards for target
        with event_logger.add_benchmarked_entry("Gathering cards from target collection."):
            target_cards = self.__get_cards_cached()

        num_new_cards = len(target_cards.new_cards_ids)

        if num_new_cards < 1:
            event_logger.add_entry("Found no new cards in a target collection of {:n} cards.".format(len(target_cards.all_cards_ids)))
            return TargetReorderResult(success=False, error="No new cards to reorder.")
        else:
            event_logger.add_entry("Found {:n} new cards in a target collection of {:n} cards.".format(num_new_cards, len(target_cards.all_cards_ids)))

        # Get corpus data

        for lang_id in [LanguageData.get_lang_id_from_data_id(lang_data_id) for lang_data_id in self.get_language_data_ids_from_config_target(self.config_target)]:
            tokenizer = TextProcessing.get_tokenizer(lang_id)
            if hasattr(tokenizer, "__name__") and "default_tokenizer" not in tokenizer.__name__:
                event_logger.add_entry("Using tokenizer '{}' for '{}'.".format(tokenizer.__name__, lang_id.upper()))

        with event_logger.add_benchmarked_entry("Creating corpus data from target cards."):
            target_corpus_data = self.__get_corpus_data_cached(target_cards, language_data)

        # If reorder scope is defined, use it for reordering
        reorder_scope_query = self.__get_reorder_scope_query()
        reorder_scope_target_cards = target_cards
        if reorder_scope_query:
            new_target_cards = self.get_cards(reorder_scope_query)
            if len(new_target_cards.all_cards_ids) == 0:
                event_logger.add_entry("Reorder scope query yielded no results!")
                return TargetReorderResult(success=False, error="Reorder scope query yielded no results!")
            elif len(new_target_cards.new_cards_ids) == 0:
                event_logger.add_entry("Reorder scope query yielded no new cards to reorder!")
                return TargetReorderResult(success=True)
            elif new_target_cards.all_cards_ids == target_cards.all_cards_ids:
                event_logger.add_entry("Reorder scope had no effect (same result as main scope of target)!")
            else:
                reorder_scope_target_cards = new_target_cards
                num_new_cards_main_scope = len(target_cards.new_cards_ids)
                num_new_card_reorder_scope = len(new_target_cards.new_cards_ids)
                if num_new_card_reorder_scope < num_new_cards_main_scope:
                    event_logger.add_entry("Reorder scope query reduced new cards from {:n} to {:n}.".format(num_new_cards_main_scope, num_new_card_reorder_scope))
                else:
                    event_logger.add_entry("Using reorder scope query, but it did not reduce the amount of new cards in target.")

        # Sort cards
        with event_logger.add_benchmarked_entry("Ranking cards and creating a new sorted list."):

            card_ranker = CardRanker(target_corpus_data, language_data, self.col, modified_dirty_notes)
            card_ranker.target_name = '#'+str(self.index_num)

            # Use any custom ranking weights defined in target definition
            for attribute in card_ranker.ranking_factors_span.keys():
                if (target_setting_val := get_float(self.config_target.get('ranking_'+attribute))) is not None:
                    card_ranker.ranking_factors_span[attribute] = target_setting_val

            # Use custom ranking weight object
            if 'ranking_factors' in self.config_target and self.config_target['ranking_factors'] is not None:
                if isinstance(self.config_target['ranking_factors'], dict) and len(self.config_target['ranking_factors']) > 0:
                    card_ranker.ranking_factors_span = {}
                    for factor in CardRanker.get_default_ranking_factors_span().keys():
                        if factor in self.config_target['ranking_factors']:
                            card_ranker.ranking_factors_span[factor] = float(self.config_target['ranking_factors'][factor])

            # use custom ideal_word_count
            if 'ideal_word_count' in self.config_target and self.config_target['ideal_word_count'] is not None:
                if isinstance(self.config_target['ideal_word_count'], list) and len(self.config_target['ideal_word_count']) == 2:
                    if all(isinstance(val, int) for val in self.config_target['ideal_word_count']):
                        card_ranker.ideal_word_count_min = self.config_target['ideal_word_count'][0]
                        card_ranker.ideal_word_count_max = self.config_target['ideal_word_count'][1]

            # Calculate ranking and sort cards
            card_rankings = card_ranker.calc_cards_ranking(target_cards, reorder_scope_target_cards)
            sorted_cards = sorted(reorder_scope_target_cards.new_cards, key=lambda card: card_rankings[card.id], reverse=True)
            sorted_cards_ids = [card.id for card in sorted_cards]

        # Reposition cards
        repositioning_required = reorder_scope_target_cards.new_cards_ids != sorted_cards_ids

        if not repositioning_required:
            event_logger.add_entry("Repositioning {:n} cards not needed for this target.".format(len(sorted_cards_ids)))
            return TargetReorderResult(success=True)

        return self.__reposition_cards(sorted_cards_ids, target_cards, repositioning_starting_from, event_logger, schedule_cards_as_new)

    def __reposition_cards(self, sorted_cards_ids: list[CardId], target_cards: TargetCards, repositioning_starting_from: int,
                           event_logger: EventLogger, schedule_cards_as_new: bool) -> TargetReorderResult:

        if schedule_cards_as_new:  # may be needed in some cases, such as older anki version (?)
            event_logger.add_entry("Scheduling cards as new before repositioning.")
            self.col.sched.schedule_cards_as_new(sorted_cards_ids)

        with event_logger.add_benchmarked_entry("Repositioning {:n} cards for this target.".format(len(sorted_cards_ids))):

            repositioning_anki_op_changes = self.col.sched.reposition_new_cards(
                card_ids=sorted_cards_ids,
                starting_from=repositioning_starting_from,
                step_size=1,
                randomize=False,
                shift_existing=True
            )

            return TargetReorderResult(success=True).with_repositioning_data(
                sorted_cards_ids=sorted_cards_ids,
                target_cards=target_cards,
                num_cards_repositioned=len(sorted_cards_ids),
                repositioning_anki_op_changes=repositioning_anki_op_changes
            )
