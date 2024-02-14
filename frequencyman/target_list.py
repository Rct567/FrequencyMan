"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from dataclasses import dataclass
import json
from typing import Optional

from anki.collection import Collection, OpChanges, OpChangesWithCount
from anki.cards import CardId, Card
from anki.notes import Note, NoteId

from .lib.utilities import is_numeric_value
from .card_ranker import CardRanker
from .target import ConfiguredTarget, TargetReorderResult, Target, ConfiguredTargetNote as ConfiguredTargetNote
from .language_data import LangDataId, LanguageData
from .lib.event_logger import EventLogger


@dataclass(frozen=True)
class TargetListReorderResult():
    reorder_result_list: list[TargetReorderResult]
    update_notes_anki_op_changes: Optional[OpChanges]
    modified_dirty_notes: dict[NoteId, Optional[Note]]
    num_cards_repositioned: int


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

    def set_targets(self, target_list: list[ConfiguredTarget]) -> tuple[int, str]:

        (validity_state, err_desc) = self.validate_target_list(target_list)
        if (validity_state == 1):
            self.target_list = [Target(target, target_num, self.col) for target_num, target in enumerate(target_list)]
        return (validity_state, err_desc)

    def has_targets(self) -> bool:
        return len(self.target_list) > 0

    def dump_json(self) -> str:
        target_list = [target.config_target for target in self.target_list]
        return json.dumps(target_list, indent=4)

    def __validate_target(self, target: ConfiguredTarget, index: int) -> tuple[int, str]:

        if not isinstance(target, dict):
            return (0, "Target #{} is not a valid type (object expected). ".format(index))
        if len(target.keys()) == 0:
            return (0, "Target #{} does not have any keys.".format(index))
        if "deck" not in target and "decks" not in target and "scope_query" not in target:
            return (0, "Target #{} is missing key 'deck', 'decks' or 'scope_query'.".format(index))
        for key in target.keys():
            if key == "":
                return (0, "Target #{} has an empty key.".format(index))
            known_keys = {"deck", "decks", "notes", "scope_query", "reorder_scope_query",
                          "ranking_factors", "familiarity_sweetspot_point", "ideal_word_count", "focus_words_endpoint"}
            known_keys.update(map(lambda s: "ranking_"+s, CardRanker.get_default_ranking_factors_span().keys()))
            if key not in known_keys:
                return (0, "Target #{} has unknown key '{}'.".format(index, key))

        # check field value for notes
        if 'notes' not in target:
            return (0, "Target object #{} is missing key 'notes'.".format(index))
        elif not isinstance(target.get('notes'), list):
            return (0, "Target object #{} value for 'notes' is not a valid type (array expected).".format(index))
        elif len(target.get('notes', [])) == 0:
            return (0, "Target object #{} value for 'notes' is empty.".format(index))

        for note_index, note in enumerate(target.get('notes', [])):
            if not isinstance(note, dict):
                return (0, "Note specified in target[{}].notes is not a valid type (object expected).".format(index))
            if "name" not in note:
                return (0, "Note object specified in target[{}].notes is missing key 'name'.".format(index))
            if "fields" not in note:
                return (0, "Note object specified in target[{}].notes is is missing key 'fields'.".format(index))
            if not isinstance(note.get('fields'), dict):
                return (0, "Fields for note object specified in target[{}].notes[{}] is not a valid type (object expected).".format(index, note_index))

            note_model = self.col.models.by_name(note['name'])

            if not note_model:
                return (0, "Name '{}' for note object specified in target[{}].notes does not exist.".format(note['name'], index))

            for field_name, lang_key in note.get('fields', {}).items():
                if not isinstance(lang_key, str):
                    return (0, "Value for field '{}' in fields object specified in target[{}].notes[{}] is not a valid type (string expected).".format(field_name, index, note_index))
                lang_data_id = LangDataId(lang_key.lower())
                if not any(field['name'] == field_name for field in note_model['flds']):
                    return (0, "Field name '{}' in fields object specified in target[{}].notes[{}] does not exist.".format(field_name, index, note_index))
                if not self.language_data.id_has_directory(lang_data_id):
                    return (0, "No directory found for key '{}' in '{}'!".format(lang_data_id, self.language_data.root_dir))

        # check custom ranking factors object and its weights values
        if 'ranking_factors' in target:
            if not isinstance(target['ranking_factors'], dict):
                return (0, "Ranking factors specified in target #{} is not a valid type (object expected).".format(index))
            if len(target['ranking_factors']) < 0:
                return (0, "Ranking factors specified in target #{} is empty.".format(index))
            allowed_keys = CardRanker.get_default_ranking_factors_span().keys()
            for key, value in target['ranking_factors'].items():
                if key not in allowed_keys:
                    return (0, "Ranking factor '{}' specified in target[{}].ranking_factors is unknown.".format(key, index))
                if not is_numeric_value(value):
                    return (0, "Value for ranking factors '{}' specified in target[{}].ranking_factors is not numeric.".format(key, index))

        # check ideal_word_count
        if 'ideal_word_count' in target:
            if not isinstance(target['ideal_word_count'], list):
                return (0, "Ideal word count specified in target #{} is not a valid type (array expected).".format(index))
            if len(target['ideal_word_count']) == 0:
                return (0, "Ideal word count specified in target #{} is empty.".format(index))
            if len(target['ideal_word_count']) != 2:
                return (0, "Ideal word count specified in target #{} should contain only two values (min and max).".format(index))
            if not all(isinstance(val, int) for val in target['ideal_word_count']):
                return (0, "Values specified for target[{}].ideal_word_count should all be a number (integer).".format(index))
            if target['ideal_word_count'][0] > target['ideal_word_count'][1]:
                return (0, "Ideal word count specified in target #{} should has a min value that is higher or equal to the max value.".format(index))

        # check custom ranking weights defined
        for key in CardRanker.get_default_ranking_factors_span().keys():
            ranking_key = 'ranking_'+key
            if ranking_key in target and not is_numeric_value(target[ranking_key]):
                return (0, "Custom ranking factors '{}' specified in target #{} has a non-numeric value.".format(ranking_key, index))

        # defined target seems valid
        return (1, "")

    def validate_target_list(self, target_data: list[ConfiguredTarget]) -> tuple[int, str]:

        if not isinstance(target_data, list):
            return (0, "Reorder target is not a list (array expected).")
        elif len(target_data) < 1:
            return (0, "Reorder target list is empty.")
        for index, target in enumerate(target_data):
            (validity_state, err_desc) = self.__validate_target(target, index)
            if validity_state == 0:
                return (0, err_desc)
        return (1, "")

    def get_targets_from_json(self, json_data: str) -> tuple[int, list[ConfiguredTarget], str]:

        if json_data == "":
            return (0, [], "")
        try:
            data: TargetList = json.loads(json_data)
            if not isinstance(data, list):
                return (0, [], "JSON does not contain a list!")
            (validity_state, err_desc) = self.validate_target_list(data)
            return (validity_state, data, err_desc)
        except json.JSONDecodeError as e:
            error_message = "Invalid JSON at line " + str(e.lineno) + "! "+e.msg+"."
            line_number = e.lineno
            content_lines = json_data.split("\n")
            if len(content_lines) > line_number-1:
                invalid_line = content_lines[line_number-1].lstrip()
                if invalid_line.strip() != "":
                    error_message += "\n\nInvalid JSON: <span class=\"alt\">" + invalid_line + "</span>"
            return (-1, [], error_message)

    def reorder_cards(self, col: Collection, event_logger: EventLogger) -> TargetListReorderResult:

        reorder_result_list: list[TargetReorderResult] = []
        modified_dirty_notes: dict[NoteId, Optional[Note]] = {}
        num_cards_repositioned = 0
        cache_data = {}

        # Reposition cards for each target
        for target in self.target_list:
            target.cache_data = cache_data
            with event_logger.add_benchmarked_entry("Reordering target #{}.".format(target.index_num)):
                reorder_result = target.reorder_cards(num_cards_repositioned+1, self.language_data, event_logger, modified_dirty_notes)
                reorder_result_list.append(reorder_result)
                if reorder_result.cards_repositioned:
                    num_cards_repositioned += reorder_result.num_cards_repositioned

        if num_cards_repositioned == 0:
            event_logger.add_entry("Order of cards from targets was already up-to-date!")

        # Update notes that have been modifies (field values for example)
        update_notes_anki_op_changes: Optional[OpChanges] = None
        num_modified_dirty_notes = len(modified_dirty_notes)
        if (num_modified_dirty_notes > 0):
            notes_to_update = [note for note in modified_dirty_notes.values() if note is not None]
            with event_logger.add_benchmarked_entry("Updating {:n} modified notes from targets.".format(len(notes_to_update))):
                update_notes_anki_op_changes = col.update_notes(notes_to_update)

        # Done
        event_logger.add_entry("Done with reordering of all targets! {:n} cards repositioned.".format(num_cards_repositioned))
        return TargetListReorderResult(
            num_cards_repositioned=num_cards_repositioned,
            reorder_result_list=reorder_result_list,
            update_notes_anki_op_changes=update_notes_anki_op_changes,
            modified_dirty_notes=modified_dirty_notes
        )
