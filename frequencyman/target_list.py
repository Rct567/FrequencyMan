"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from dataclasses import dataclass
from enum import Enum
import json
from typing import Optional, Tuple

from anki.collection import Collection, OpChanges, OpChangesWithCount
from anki.cards import CardId, Card
from anki.notes import Note, NoteId

from .target_cards import TargetCards
from .lib.utilities import batched, is_numeric_value
from .card_ranker import CardRanker
from .target import ConfiguredTarget, ConfiguredTargetData, TargetReorderResult, Target, ConfiguredTargetDataNote as ConfiguredTargetDataNote, ValidConfiguredTarget
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
    targets_defined: list[ConfiguredTarget]
    err_desc: str
    valid_targets_defined: Optional[list[ValidConfiguredTarget]]


class TargetList:

    target_list: list[Target]
    language_data: LanguageData
    col: Collection

    def __init__(self, language_data: LanguageData, col: Collection) -> None:
        self.target_list = []
        self.language_data = language_data
        self.col = col

    def __iter__(self):
        return iter(self.target_list)

    def __len__(self):
        return len(self.target_list)

    def __getitem__(self, index: int) -> Target:
        return self.target_list[index]

    def set_valid_targets(self, valid_target_list: list[ValidConfiguredTarget]) -> None:

        self.target_list = [Target(target, target_num, self.col) for target_num, target in enumerate(valid_target_list)]

    def set_targets(self, target_list_data: list[ConfiguredTargetData]):

        target_list = [ConfiguredTarget(target) for target in target_list_data]
        (validity_state, err_desc, valid_target_list) = TargetList.validate_target_list(target_list, self.col, self.language_data)

        if validity_state != JsonTargetsValidity.VALID_TARGETS or valid_target_list is None:
            raise Exception(err_desc)

        self.set_valid_targets(valid_target_list)

    def has_targets(self) -> bool:
        return len(self.target_list) > 0

    def dump_json(self) -> str:
        target_list = [target.config_target.data for target in self.target_list]
        return json.dumps(target_list, indent=4)

    @staticmethod
    def __validate_target(target: ConfiguredTarget, index: int, col: Collection, language_data: LanguageData) -> tuple[bool, str]:

        if not isinstance(target, ConfiguredTarget):
            return (False, "Target #{} is not a valid type (object expected). ".format(index))
        if len(target.keys()) == 0:
            return (False, "Target #{} does not have any keys.".format(index))
        if "deck" not in target and "decks" not in target and "scope_query" not in target:
            return (False, "Target #{} is missing key 'deck', 'decks' or 'scope_query'.".format(index))
        for key in target.keys():
            if key == "":
                return (False, "Target #{} has an empty key.".format(index))
            known_keys = {"deck", "decks", "notes", "scope_query", "reorder_scope_query", "ranking_factors",
                          "familiarity_sweetspot_point", "suspended_card_value", "suspended_leech_card_value",
                          "ideal_word_count", "focus_words_endpoint", "corpus_segmentation_strategy"}
            known_keys.update(map(lambda s: "ranking_"+s, CardRanker.get_default_ranking_factors_span().keys()))
            if key not in known_keys:
                return (False, "Target #{} has unknown key '{}'.".format(index, key))

        # check deck names
        for deck_name in Target.get_deck_names_from_config_target(target):
            if col.decks.id_for_name(deck_name) is None:
                return (False, "Deck '{}' defined in target #{} not found.".format(deck_name, index))

        # check field value for notes
        if 'notes' not in target:
            return (False, "Target object #{} is missing key 'notes'.".format(index))
        elif not isinstance(target.get('notes'), list):
            return (False, "Target object #{} value for 'notes' is not a valid type (array expected).".format(index))
        elif len(target.get('notes', [])) == 0:
            return (False, "Target object #{} value for 'notes' is empty.".format(index))

        for note_index, note in enumerate(target.get('notes', [])):
            if not isinstance(note, dict):
                return (False, "Note specified in target[{}].notes is not a valid type (object expected).".format(index))
            if "name" not in note:
                return (False, "Note object specified in target[{}].notes is missing key 'name'.".format(index))
            if "fields" not in note:
                return (False, "Note object specified in target[{}].notes is is missing key 'fields'.".format(index))
            if not isinstance(note.get('fields'), dict):
                return (False, "Fields for note object specified in target[{}].notes[{}] is not a valid type (object expected).".format(index, note_index))

            note_model = col.models.by_name(note['name'])

            if not note_model:
                return (False, "Name '{}' for note object specified in target[{}].notes does not exist.".format(note['name'], index))

            if len(note.get('fields', {})) == 0:
                return (False, "Fields object specified in target[{}].notes[{}] is empty.".format(index, note_index))

            for field_name, lang_key in note.get('fields', {}).items():
                if field_name == "":
                    return (False, "Field name in fields object specified in target[{}].notes[{}] is empty.".format(index, note_index))
                if not any(field['name'] == field_name for field in note_model['flds']):
                    return (False, "Field name '{}' in fields object specified in target[{}].notes[{}] does not exist.".format(field_name, index, note_index))
                if not isinstance(lang_key, str):
                    return (False, "Value for field '{}' in fields object specified in target[{}].notes[{}] is not a valid type (string expected).".format(field_name, index, note_index))
                if lang_key == "":
                    return (False, "Value for field '{}' in fields object specified in target[{}].notes[{}] is empty (lang_data_id expected).".format(field_name, index, note_index))
                lang_data_id = LangDataId(lang_key.lower())
                if not language_data.id_has_directory(lang_data_id):
                    return (False, "No directory found for lang_data_id '{}' in '{}'!".format(lang_data_id, language_data.data_dir))

        # check custom ranking factors object and its weights values
        if 'ranking_factors' in target:
            if not isinstance(target['ranking_factors'], dict):
                return (False, "Ranking factors specified in target #{} is not a valid type (object expected).".format(index))
            if len(target['ranking_factors']) < 0:
                return (False, "Ranking factors specified in target #{} is empty.".format(index))
            allowed_keys = CardRanker.get_default_ranking_factors_span().keys()
            for key, value in target['ranking_factors'].items():
                if key not in allowed_keys:
                    return (False, "Ranking factor '{}' specified in target[{}].ranking_factors is unknown.".format(key, index))
                if not is_numeric_value(value):
                    return (False, "Value for ranking factors '{}' specified in target[{}].ranking_factors is not numeric.".format(key, index))

        # check ideal_word_count
        if 'ideal_word_count' in target:
            if not isinstance(target['ideal_word_count'], list):
                return (False, "Ideal word count specified in target #{} is not a valid type (array expected).".format(index))
            if len(target['ideal_word_count']) == 0:
                return (False, "Ideal word count specified in target #{} is empty.".format(index))
            if len(target['ideal_word_count']) != 2:
                return (False, "Ideal word count specified in target #{} should contain only two values (min and max).".format(index))
            if not all(isinstance(val, int) for val in target['ideal_word_count']):
                return (False, "Values specified for target[{}].ideal_word_count should all be a number (integer).".format(index))
            if target['ideal_word_count'][0] > target['ideal_word_count'][1]:
                return (False, "Ideal word count specified in target #{} should has a min value that is higher or equal to the max value.".format(index))

        # check custom ranking weights defined
        for key in CardRanker.get_default_ranking_factors_span().keys():
            ranking_key = 'ranking_'+key
            if ranking_key in target and not is_numeric_value(target[ranking_key]):
                return (False, "Custom ranking factors '{}' specified in target #{} has a non-numeric value.".format(ranking_key, index))

        # defined target seems valid
        return (True, "")

    @staticmethod
    def validate_target_list(target_data: list[ConfiguredTarget], col: Collection, language_data: LanguageData) -> tuple[JsonTargetsValidity, str, Optional[list[ValidConfiguredTarget]]]:

        if not isinstance(target_data, list):
            return (JsonTargetsValidity.INVALID_TARGETS, "Reorder target is not a list (array expected).", None)
        elif len(target_data) < 1:
            return (JsonTargetsValidity.INVALID_TARGETS, "Reorder target list is empty.", None)

        for index, target in enumerate(target_data):
            (target_is_valid, err_desc) = TargetList.__validate_target(target, index, col, language_data)
            if not target_is_valid:
                return (JsonTargetsValidity.INVALID_TARGETS, err_desc, None)

        return (JsonTargetsValidity.VALID_TARGETS, "", [ValidConfiguredTarget(target.data) for target in target_data])

    @staticmethod
    def get_targets_from_json(json_data: str, col: Collection, language_data: LanguageData) -> JsonTargetsResult:

        if json_data == "":
            return JsonTargetsResult(JsonTargetsValidity.INVALID_TARGETS, [], "", None)
        try:
            data = json.loads(json_data)
            if not isinstance(data, list):
                return JsonTargetsResult(JsonTargetsValidity.INVALID_TARGETS, [], "Reorder target is not a list (array expected).", [])
            (validity_state, err_desc, valid_target_list) = TargetList.validate_target_list([ConfiguredTarget(target) for target in data], col, language_data)
            return JsonTargetsResult(validity_state, [ConfiguredTarget(target) for target in data], err_desc, valid_target_list)
        except json.JSONDecodeError as e:
            error_message = "Invalid JSON at line " + str(e.lineno) + "! "+e.msg+"."
            line_number = e.lineno
            content_lines = json_data.split("\n")
            if len(content_lines) > line_number-1:
                invalid_line = content_lines[line_number-1].lstrip()
                if invalid_line.strip() != "":
                    error_message += "\n\nInvalid JSON: <span class=\"alt\">" + invalid_line + "</span>"
            return JsonTargetsResult(JsonTargetsValidity.INVALID_JSON, [], error_message, None)

    def reorder_cards(self, col: Collection, event_logger: EventLogger, schedule_cards_as_new: bool = False) -> TargetListReorderResult:

        reorder_result_list: list[TargetReorderResult] = []
        modified_dirty_notes: dict[NoteId, Optional[Note]] = {}
        num_cards_repositioned = 0
        num_targets_repositioned = 0
        cache_data = {}

        # Reposition cards for each target
        for target in self.target_list:
            target.cache_data = cache_data
            with event_logger.add_benchmarked_entry("Reordering target #{}.".format(target.index_num)):
                reorder_result = target.reorder_cards(num_cards_repositioned, self.language_data, event_logger, modified_dirty_notes, schedule_cards_as_new)
                reorder_result_list.append(reorder_result)
                if reorder_result.cards_repositioned:
                    num_cards_repositioned += reorder_result.num_cards_repositioned
                    num_targets_repositioned += 1

        if num_cards_repositioned == 0:
            event_logger.add_entry("Order of cards from targets was already up-to-date!")

        # Clear cache
        TargetCards.notes_from_cards_cached = {}

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
        event_logger.add_entry("Done with reordering of all targets! {:n} cards repositioned.".format(num_cards_repositioned))
        return TargetListReorderResult(
            num_cards_repositioned=num_cards_repositioned,
            num_targets_repositioned=num_targets_repositioned,
            reorder_result_list=reorder_result_list,
            update_notes_anki_op_changes=update_notes_anki_op_changes,
            modified_dirty_notes=modified_dirty_notes
        )
