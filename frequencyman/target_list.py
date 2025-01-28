"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from dataclasses import dataclass
from enum import Enum
from functools import cache
import json
import re
from typing import Iterator, Optional, Any

from anki.collection import Collection, OpChanges, OpChangesWithCount
from anki.cards import CardId, Card
from anki.notes import Note, NoteId

from .lib.persistent_cacher import PersistentCacher
from .configured_target import ConfiguredTarget
from .target_corpus_data import CorpusSegmentationStrategy
from .target_cards import TargetCards
from .lib.utilities import JSON_TYPE, batched, get_float, load_json, profile_context, var_dump_log
from .target import ConfiguredTargetNote, TargetCacheData, TargetReorderResult, Target, ValidConfiguredTarget, CardRanker
from .language_data import LangDataId, LanguageData
from .lib.event_logger import EventLogger


@dataclass(frozen=True)
class TargetListReorderResult():
    reorder_result_list: list[TargetReorderResult]
    update_notes_anki_op_changes: list[OpChanges]
    modified_dirty_notes: dict[NoteId, Optional[Note]]
    num_cards_repositioned: int
    num_targets_repositioned: int


class JsonTargetsValidity(Enum):
    INVALID_JSON = -1
    INVALID_TARGETS = 0
    VALID_TARGETS = 1


@dataclass
class JsonTargetsResult():
    validity_state: JsonTargetsValidity
    targets_defined: list[JSON_TYPE]
    err_desc: str
    valid_targets_defined: Optional[list[ValidConfiguredTarget]]


class TargetList:

    target_list: list[Target]
    language_data: LanguageData
    col: Collection

    def __init__(self, language_data: LanguageData, cacher: PersistentCacher, col: Collection) -> None:
        self.target_list = []
        self.language_data = language_data
        self.col = col
        self.cacher = cacher

    def __iter__(self) -> Iterator[Target]:
        return iter(self.target_list)

    def __len__(self) -> int:
        return len(self.target_list)

    def __getitem__(self, index: int) -> Target:
        return self.target_list[index]

    def __set_new_targets_data_cache(self) -> None:

        cache_data: TargetCacheData = {'corpus': {}, 'target_cards': {}}

        for target in self.target_list:
            target.cache_data = cache_data

    def set_valid_targets(self, valid_target_list: list[ValidConfiguredTarget]) -> None:

        self.target_list = [Target(target, target_num, self.col, self.language_data, self.cacher) for target_num, target in enumerate(valid_target_list)]
        self.__set_new_targets_data_cache()

    def set_targets_from_json(self, target_list_data: JSON_TYPE) -> None:

        (validity_state, err_desc, valid_target_list) = TargetList.validate_target_list(target_list_data, self.col, self.language_data)

        if validity_state != JsonTargetsValidity.VALID_TARGETS or valid_target_list is None:
            raise Exception(err_desc)

        self.set_valid_targets(valid_target_list)

    def set_targets(self, target_list_data: list[JSON_TYPE]) -> None:
        return self.set_targets_from_json(target_list_data)

    def has_targets(self) -> bool:
        return len(self.target_list) > 0

    def dump_json(self) -> str:
        target_list = [target.config_target for target in self.target_list]
        return json.dumps(target_list, indent=4, ensure_ascii=False)

    @staticmethod
    def get_targets_from_json(json_data: str, col: Collection, language_data: LanguageData) -> JsonTargetsResult:

        if json_data == "":
            return JsonTargetsResult(JsonTargetsValidity.INVALID_TARGETS, [], "", None)
        try:
            data = load_json(json_data)
            if not isinstance(data, list):
                return JsonTargetsResult(JsonTargetsValidity.INVALID_TARGETS, [], "Reorder target is not a list (array expected).", None)
            (validity_state, err_desc, valid_target_list) = TargetList.validate_target_list(data, col, language_data)
            return JsonTargetsResult(validity_state, data, err_desc, valid_target_list)
        except json.JSONDecodeError as e:
            error_message = "Invalid JSON at line " + str(e.lineno) + "! "+e.msg+"."
            line_number = e.lineno
            content_lines = json_data.split("\n")
            if len(content_lines) > line_number-1:
                invalid_line = content_lines[line_number-1].lstrip()
                if invalid_line.strip() != "":
                    error_message += "\n\nInvalid JSON: <span class=\"alt\">" + invalid_line + "</span>"
            return JsonTargetsResult(JsonTargetsValidity.INVALID_JSON, [], error_message, None)

    @staticmethod
    def validate_target_list(targets_data: JSON_TYPE, col: Collection, language_data: LanguageData) -> tuple[JsonTargetsValidity, str, Optional[list[ValidConfiguredTarget]]]:

        if not isinstance(targets_data, list):
            return (JsonTargetsValidity.INVALID_TARGETS, "Reorder target is not a list (array expected).", None)
        elif len(targets_data) < 1:
            return (JsonTargetsValidity.INVALID_TARGETS, "Reorder target list is empty.", None)

        # validate targets and create list of valid targets

        valid_target_list: list[ValidConfiguredTarget] = []

        for index, target_data in enumerate(targets_data):
            (target_is_valid, err_desc, valid_target) = TargetList.__validate_target_data(target_data, index, col, language_data)
            if not target_is_valid:
                return (JsonTargetsValidity.INVALID_TARGETS, err_desc, None)
            elif valid_target is not None:
                valid_target_list.append(valid_target)

        # check uniqueness of target ids

        target_ids: set[str] = set()

        for index, target in enumerate(targets_data):
            if not isinstance(target, dict) or 'id' not in target or not isinstance(target['id'], str):
                continue
            if target['id'] in target_ids:
                return (JsonTargetsValidity.INVALID_TARGETS, "ID '{}' defined in target #{} is not unique.".format(target['id'], index), None)
            target_ids.add(target['id'])

        # targets are valid

        return (JsonTargetsValidity.VALID_TARGETS, "", valid_target_list)

    @staticmethod
    @cache
    def __query_executes_validly(query: str, col: Collection) -> bool:

        if len(query.strip()) == 0:
            return True

        try:
            col.find_cards("deck:NoneExisting AND ({})".format(query))
            return True
        except Exception:
            return False

    @staticmethod
    def is_valid_query(query: Any, col: Collection) -> bool:

        if not isinstance(query, str):
            return False

        if re.match(r"^[a-zA-Z0-9_\s]+$", query):
            return True

        return TargetList.__query_executes_validly(query, col)

    @staticmethod
    def __validate_target_data(target_data: JSON_TYPE, index: int, col: Collection, language_data: LanguageData) -> tuple[bool, str, Optional[ValidConfiguredTarget]]:

        if not isinstance(target_data, dict):
            return (False, "Target #{} is not a valid type (object expected). ".format(index), None)
        if len(target_data.keys()) == 0:
            return (False, "Target #{} does not have any keys.".format(index), None)
        if "deck" not in target_data and "decks" not in target_data and "scope_query" not in target_data:
            return (False, "Target #{} is missing key 'deck', 'decks' or 'scope_query'.".format(index), None)

        result = ValidConfiguredTarget(notes=[])

        # handle renamed ranking factors

        renamed_ranking_factors = {'ideal_unseen_word_count': 'ideal_new_word_count', 'reinforce_focus_words': 'reinforce_learning_words'}

        for old_factor_name, new_factor_name in renamed_ranking_factors.items():
            if 'ranking_'+old_factor_name in target_data:
                target_data['ranking_'+new_factor_name] = target_data['ranking_'+old_factor_name]
                del target_data['ranking_'+old_factor_name]

        if 'ranking_factors' in target_data and isinstance(target_data['ranking_factors'], dict) and len(target_data['ranking_factors']) > 0:
            for old_factor_name, new_factor_name in renamed_ranking_factors.items():
                if old_factor_name in target_data['ranking_factors']:
                    target_data['ranking_factors'][new_factor_name] = target_data['ranking_factors'][old_factor_name]
                    del target_data['ranking_factors'][old_factor_name]

        # check id

        if 'id' in target_data:
            if not isinstance(target_data['id'], str):
                return (False, "ID defined in target #{} is not a string (string expected).".format(index), None)
            elif len(target_data['id']) == 0:
                return (False, "ID defined in target #{} is empty.".format(index), None)
            elif not re.match(r"^[a-zA-Z0-9_]+$", target_data['id']):
                return (False, "ID defined in target #{} is not a valid identifier (only letters, numbers and underscores are allowed).".format(index), None)
            result['id'] = target_data['id']

        # check deck names

        if 'deck' in target_data:
            if not isinstance(target_data['deck'], str):
                return (False, "Deck defined in target #{} is not a string (string expected).".format(index), None)
            elif len(target_data['deck']) == 0:
                return (False, "Deck defined in target #{} is empty.".format(index), None)
            result['deck'] = target_data['deck']

        if 'decks' in target_data:
            if isinstance(target_data['decks'], list):
                if not all(isinstance(deck_name, str) for deck_name in target_data['decks']):
                    return (False, "Decks defined in target #{} is not an array of strings (strings expected in array).".format(index), None)
                if not all(deck_name != "" for deck_name in target_data['decks']):
                    return (False, "One ore more decks defined in target #{} is empty.".format(index), None)
                result['decks'] = [deck_name for deck_name in target_data['decks'] if isinstance(deck_name, str)]
            elif isinstance(target_data['decks'], str):
                if len(target_data['decks']) == 0:
                    return (False, "Decks defined in target #{} is empty.".format(index), None)
                result['decks'] = target_data['decks']
            else:
                return (False, "Decks defined in target #{} is not a string or a list or strings.".format(index), None)

        #
        if 'scope_query' in target_data:
            if not isinstance(target_data['scope_query'], str):
                return (False, "Scope query defined in target #{} is not a string (string expected).".format(index), None)
            if len(target_data['scope_query'].strip()) == 0:
                return (False, "Scope query defined in target #{} is empty.".format(index), None)
            if not TargetList.is_valid_query(target_data['scope_query'], col):
                return (False, "Scope query defined in target #{} is not a valid query.".format(index), None)
            result['scope_query'] = target_data['scope_query']

        defined_decks = ConfiguredTarget.get_deck_names_from_config_target(target_data.get('deck'), target_data.get('decks'))

        if 'scope_query' not in result and len(defined_decks) == 0:
            return (False, "Target #{} has an invalid deck defined using deck, decks or scope_query.".format(index), None)

        if len(defined_decks) > 0:
            for deck_name in defined_decks:
                if col.decks.id_for_name(deck_name) is None:
                    return (False, "Deck '{}' defined in target #{} not found.".format(deck_name, index), None)

        if 'reorder_scope_query' in target_data:
            if not isinstance(target_data['reorder_scope_query'], str):
                return (False, "Reorder scope query defined in target #{} is not a string (string expected).".format(index), None)
            if len(target_data['reorder_scope_query'].strip()) == 0:
                return (False, "Reorder scope query defined in target #{} is empty.".format(index), None)
            if not TargetList.is_valid_query(target_data['reorder_scope_query'], col):
                return (False, "Reorder scope query defined in target #{} is not a valid query.".format(index), None)
            result['reorder_scope_query'] = target_data['reorder_scope_query']

        # check all keys

        known_keys = ValidConfiguredTarget.get_valid_keys()

        for key in target_data.keys():
            if key == "":
                return (False, "Target #{} has an empty key.".format(index), None)
            if key not in known_keys:
                return (False, "Target #{} has unknown key '{}'.".format(index, key), None)

        # check ideal_word_count
        if 'ideal_word_count' in target_data:
            if not isinstance(target_data['ideal_word_count'], list):
                return (False, "Ideal word count specified in target #{} is not a valid type (array expected).".format(index), None)
            if len(target_data['ideal_word_count']) == 0:
                return (False, "Ideal word count specified in target #{} is empty.".format(index), None)
            if len(target_data['ideal_word_count']) != 2:
                return (False, "Ideal word count specified in target #{} should contain only two values (min and max).".format(index), None)
            if not isinstance(target_data['ideal_word_count'][0], int):
                return (False, "Value for 'ideal_word_count' min specified in target[{}] is not a number (integer).".format(index), None)
            if not isinstance(target_data['ideal_word_count'][1], int):
                return (False, "Value for 'ideal_word_count' max specified in target[{}] is not a number (integer).".format(index), None)
            if target_data['ideal_word_count'][0] > target_data['ideal_word_count'][1]:
                return (False, "Ideal word count specified in target #{} should has a min value that is higher or equal to the max value.".format(index), None)
            result['ideal_word_count'] = [int(val) for val in target_data['ideal_word_count'] if val is not None and isinstance(val, int)]

        if 'familiarity_sweetspot_point' in target_data:
            if isinstance(target_data['familiarity_sweetspot_point'], float) or isinstance(target_data['familiarity_sweetspot_point'], int):
                result['familiarity_sweetspot_point'] = float(target_data['familiarity_sweetspot_point'])
            elif isinstance(target_data['familiarity_sweetspot_point'], str):
                result['familiarity_sweetspot_point'] = target_data['familiarity_sweetspot_point']
            else:
                return (False, "Familiarity sweetspot point defined in target #{} is not a number of string.".format(index), None)

        if 'focus_words_max_familiarity' in target_data:
            if isinstance(target_data['focus_words_max_familiarity'], float) or isinstance(target_data['focus_words_max_familiarity'], int):
                result['focus_words_max_familiarity'] = float(target_data['focus_words_max_familiarity'])
            else:
                return (False, "Maximum familiarity for focus words defined in target #{} is not a number.".format(index), None)

        if 'suspended_card_value' in target_data:
            if isinstance(target_data['suspended_card_value'], float) or isinstance(target_data['suspended_card_value'], int):
                result['suspended_card_value'] = float(target_data['suspended_card_value'])
            else:
                return (False, "Suspended card value defined in target #{} is not a number.".format(index), None)

        if 'suspended_leech_card_value' in target_data:
            if isinstance(target_data['suspended_leech_card_value'], float) or isinstance(target_data['suspended_leech_card_value'], int):
                result['suspended_leech_card_value'] = float(target_data['suspended_leech_card_value'])
            else:
                return (False, "Suspended leech card value defined in target #{} is not a number.".format(index), None)

        if 'corpus_segmentation_strategy' in target_data:
            if not isinstance(target_data['corpus_segmentation_strategy'], str):
                return (False, "Corpus segmentation strategy defined in target #{} is not a string (string expected).".format(index), None)
            if len(target_data['corpus_segmentation_strategy']) == 0:
                return (False, "Corpus segmentation strategy defined in target #{} is empty.".format(index), None)
            if len(target_data['corpus_segmentation_strategy']) < 4:
                return (False, "Corpus segmentation strategy defined in target #{} is too short (at least 4 characters expected).".format(index), None)
            known_keys = set(CorpusSegmentationStrategy.__members__.keys())
            if target_data['corpus_segmentation_strategy'].upper() not in known_keys:
                return (False, "Corpus segmentation strategy '{}' defined in target #{} is unknown.".format(target_data['corpus_segmentation_strategy'], index), None)
            result['corpus_segmentation_strategy'] = target_data['corpus_segmentation_strategy'].lower()

        if ConfiguredTarget.get_query_from_defined_main_scope(target_data.get('deck'), target_data.get('decks'), target_data.get('scope_query')) is None:
            return (False, "Target #{} has an invalid scope defined using deck, decks or scope_query.".format(index), None)

        # custom ranking factors object

        if 'ranking_factors' in target_data:
            if not isinstance(target_data['ranking_factors'], dict) or not all(isinstance(key, str) for key in target_data['ranking_factors']):
                return (False, "Ranking factors defined in target #{} is not a valid object.".format(index), None)
            if len(target_data['ranking_factors']) == 0:
                return (False, "Ranking factors defined in target #{} is empty.".format(index), None)
            if not all(get_float(val) is not None for val in target_data['ranking_factors'].values()):
                return (False, "Ranking factors defined in target #{} is not a object with numbers values.".format(index), None)

            result['ranking_factors'] = {}
            allowed_keys = CardRanker.get_default_ranking_factors_span().keys()
            for key, val in target_data['ranking_factors'].items():
                if key not in allowed_keys:
                    return (False, "Ranking factor '{}' specified in target[{}].ranking_factors is unknown.".format(key, index), None)
                float_val = get_float(val)
                if float_val is None:
                    return (False, "Value for ranking factors '{}' specified in target[{}].ranking_factors is not numeric.".format(key, index), None)
                result['ranking_factors'][key] = float_val

        # check custom ranking weights defined

        for key in CardRanker.get_default_ranking_factors_span().keys():
            ranking_key = 'ranking_'+key
            if ranking_key in target_data:
                float_val = get_float(target_data[ranking_key])
                if float_val is None:
                    return (False, "Custom ranking factors '{}' specified in target #{} has a non-numeric value.".format(ranking_key, index), None)
                else:
                    result.set_custom_ranking_weight(ranking_key, float_val)

        # check notes

        if 'notes' not in target_data:
            return (False, "Target object #{} is missing key 'notes'.".format(index), None)
        elif not isinstance(target_data['notes'], list):
            return (False, "Target object #{} value for 'notes' is not a valid type (array expected).".format(index), None)
        elif len(target_data['notes']) == 0:
            return (False, "Target object #{} value for 'notes' is empty.".format(index), None)

        for note_index, note in enumerate(target_data['notes']):
            if not isinstance(note, dict):
                return (False, "Note specified in target[{}].notes is not a valid type (object expected).".format(index), None)
            if "name" not in note:
                return (False, "Note object specified in target[{}].notes does not have a valid 'name' (string expected).".format(index), None)
            if not isinstance(note['name'], str):
                return (False, "Note object specified in target[{}].notes does not have a valid 'name' (string expected).".format(index), None)
            if "fields" not in note:
                return (False, "Note object specified in target[{}].notes is is missing key 'fields'.".format(index), None)
            if not isinstance(note['fields'], dict):
                return (False, "Fields for note object specified in target[{}].notes[{}] is not a valid type (object expected).".format(index, note_index), None)
            if len(note['fields']) == 0:
                return (False, "Fields object specified in target[{}].notes[{}] is empty.".format(index, note_index), None)

            note_model = col.models.by_name(note['name'])

            if not note_model:
                return (False, "Name '{}' for note object specified in target[{}].notes does not exist.".format(note['name'], index), None)

            note_fields: dict[str, str] = {}
            for field_name, lang_data_id in note['fields'].items():
                if field_name == "":
                    return (False, "Field name in fields object specified in target[{}].notes[{}] is empty.".format(index, note_index), None)
                if not any(field['name'] == field_name for field in note_model['flds']):
                    return (False, "Field name '{}' in fields object specified in target[{}].notes[{}] does not exist.".format(field_name, index, note_index), None)
                if not isinstance(lang_data_id, str):
                    return (False, "Value for field '{}' in fields object specified in target[{}].notes[{}] is not a valid type (string expected).".format(field_name, index, note_index), None)
                if lang_data_id == "":
                    return (False, "Value for field '{}' in fields object specified in target[{}].notes[{}] is empty (lang_data_id expected).".format(field_name, index, note_index), None)
                lang_data_id = LangDataId(lang_data_id.lower())
                if not language_data.id_has_directory(lang_data_id):
                    return (False, "No directory found for lang_data_id '{}' in '{}'!".format(lang_data_id, language_data.data_dir), None)

            note_fields = {field_name: str(lang_data_id) for field_name, lang_data_id in note['fields'].items()}
            result['notes'].append(ConfiguredTargetNote(name=note['name'], fields=note_fields))

        # defined target seems valid

        ordered_result = {}

        for key in target_data.keys():
            if key in result:
                ordered_result[key] = result.get(key)

        return (True, "", ValidConfiguredTarget(**ordered_result))

    def reorder_cards(self, col: Collection, event_logger: EventLogger) -> TargetListReorderResult:

        reorder_result_list: list[TargetReorderResult] = []
        modified_dirty_notes: dict[NoteId, Optional[Note]] = {}
        num_cards_repositioned = 0
        num_targets_repositioned = 0

        # Reposition cards for each target
        for target in self.target_list:
            with event_logger.add_benchmarked_entry("Reordering target #{}.".format(target.index_num)):
                reorder_result = target.reorder_cards(num_cards_repositioned, event_logger, modified_dirty_notes)
                reorder_result_list.append(reorder_result)
                if reorder_result.cards_repositioned:
                    num_cards_repositioned += reorder_result.num_cards_repositioned
                    num_targets_repositioned += 1

        self.cacher.db.close()

        if num_cards_repositioned == 0:
            event_logger.add_entry("Order of cards from targets was already up-to-date!")

        # Clear cache
        TargetCards.notes_from_cards_cached.clear()
        TargetCards.leech_card_ids_cached.clear()
        self.__set_new_targets_data_cache()

        # Update notes that have been modifies (field values for example)
        update_notes_anki_op_changes: list[OpChanges] = []
        num_modified_dirty_notes = len(modified_dirty_notes)
        if (num_modified_dirty_notes > 0):
            notes_to_update = [note for note in modified_dirty_notes.values() if note is not None]
            with event_logger.add_benchmarked_entry("Updating {:n} modified notes from targets.".format(len(notes_to_update))):
                for notes in batched(notes_to_update, 4_000):
                    op_changes = col.update_notes(notes, skip_undo_entry=True)
                    update_notes_anki_op_changes.append(op_changes)

        # Done
        event_logger.add_entry("Done with reordering of all targets!")
        event_logger.add_entry("{:n} cards repositioned in {:.2f} seconds.".format(num_cards_repositioned, event_logger.getElapsedTime()))

        return TargetListReorderResult(
            num_cards_repositioned=num_cards_repositioned,
            num_targets_repositioned=num_targets_repositioned,
            reorder_result_list=reorder_result_list,
            update_notes_anki_op_changes=update_notes_anki_op_changes,
            modified_dirty_notes=modified_dirty_notes
        )
