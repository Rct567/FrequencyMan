from dataclasses import dataclass
import json
from typing import Optional

from anki.collection import Collection, OpChanges, OpChangesWithCount
from anki.cards import CardId, Card
from anki.notes import Note, NoteId

from .target import ConfigTargetData, TargetReorderResult, Target, ConfigTargetDataNotes
from .word_frequency_list import WordFrequencyLists
from .lib.event_logger import EventLogger


@dataclass(frozen=True)
class TargetListReorderResult():
    reorder_result_list: list[TargetReorderResult]
    repositioning_anki_op_changes: Optional[OpChangesWithCount]
    update_notes_anki_op_changes: Optional[OpChanges]


class TargetList:

    target_list: list[Target]
    word_frequency_lists: WordFrequencyLists
    col: Collection

    def __init__(self, word_frequency_lists: WordFrequencyLists, col: Collection) -> None:
        self.target_list = []
        self.word_frequency_lists = word_frequency_lists
        self.col = col

    def __iter__(self):
        return iter(self.target_list)

    def __len__(self):
        return len(self.target_list)

    def __getitem__(self, index: int) -> Target:
        return self.target_list[index]

    def set_targets(self, target_list: list[ConfigTargetData]) -> tuple[int, str]:
        (validity_state, err_desc) = self.validate_list(target_list)
        if (validity_state == 1):
            self.target_list = [Target(target, target_num) for target_num, target in enumerate(target_list)]
        return (validity_state, err_desc)

    def has_targets(self) -> bool:
        return len(self.target_list) > 0

    def dump_json(self) -> str:
        target_list = [target.target for target in self.target_list]
        return json.dumps(target_list, indent=4)

    def validate_target(self, target: ConfigTargetData, index: int) -> tuple[int, str]:
        if not isinstance(target, dict):
            return (0, "Target #{} is not a valid type (object expected). ".format(index))
        if len(target.keys()) == 0:
            return (0, "Target #{} does not have any keys.".format(index))
        if "deck" not in target.keys() and "decks" not in target.keys() and "scope_query" not in target.keys():
            return (0, "Target #{} is missing key 'deck', 'decks' or 'scope_query'.".format(index))
        for key in target.keys():
            if key == "":
                return (0, "Target #{} has an empty key.".format(index))
            elif key not in ("deck", "decks", "notes", "scope_query") and not key.startswith("ranking_"):
                return (0, "Target #{} has unknown key '{}'.".format(index, key))
        # check field value for notes
        if 'notes' not in target.keys():
            return (0, "Target object #{} is missing key 'notes'.".format(index))
        elif not isinstance(target.get('notes'), list):
            return (0, "Target object #{} value for 'notes' is not a valid type (array expected).".format(index))
        elif len(target.get('notes', [])) == 0:
            return (0, "Target object #{} value for 'notes' is empty.".format(index))

        for note in target.get('notes', []):
            if not isinstance(note, dict):
                return (0, "Note specified in target[{}].notes is not a valid type (object expected).".format(index))
            if "name" not in note:
                return (0, "Note object specified in target[{}].notes is missing key 'name'.".format(index))
            if "fields" not in note:
                return (0, "Note object specified in target[{}].notes is is missing key 'fields'.".format(index))

            note_model = self.col.models.by_name(note.get('name'))

            if not note_model:
                return (0, "Name '{}' for note object specified in target[{}].notes does not exist.".format(note.get('name'), index))

            for field_name, defined_lang_key in note.get('fields', {}).items():
                if not any(field['name'] == field_name for field in note_model['flds']):
                    return (0, "Field name '{}' for note object specified in target[{}].notes does not exist.".format(field_name, index))
                if not self.word_frequency_lists.str_key_has_frequency_list_file(defined_lang_key):
                    return (0, "No word frequency list file found for key '{}'!".format(defined_lang_key))

        return (1, "")

    def validate_list(self, target_data: list[ConfigTargetData]) -> tuple[int, str]:
        if not isinstance(target_data, list):
            return (0, "Reorder target is not a list (array expected).")
        elif len(target_data) < 1:
            return (0, "Reorder target list is empty.")
        for index, target in enumerate(target_data):
            (validity_state, err_desc) = self.validate_target(target, index)
            if validity_state == 0:
                return (0, err_desc)
        return (1, "")

    def handle_json(self, json_data: str) -> tuple[int, list[ConfigTargetData], str]:
        if json_data == "":
            return (0, [], "")
        try:
            data: TargetList = json.loads(json_data)
            if not isinstance(data, list):
                return (0, [], "JSON does not contain a list!")
            (validity_state, err_desc) = self.validate_list(data)
            return (validity_state, data, err_desc)
        except json.JSONDecodeError as e:
            return (-1, [], "Invalid JSON! ({})".format(e.msg))

    def reorder_cards(self, col: Collection, event_logger: EventLogger) -> TargetListReorderResult:

        reorder_result_list: list[TargetReorderResult] = []
        sorted_cards_ids: list[CardId] = []
        modified_dirty_notes: dict[NoteId, Note] = {}
        repositioning_required = False
        repositioning_anki_op_changes: Optional[OpChangesWithCount] = None
        update_notes_anki_op_changes: Optional[OpChanges] = None

        for target in self.target_list:
            with event_logger.add_benchmarked_entry(f"Reordering target #{target.index_num}."):
                reorder_result = target.reorder_cards(self.word_frequency_lists, col, event_logger)
                reorder_result_list.append(reorder_result)
                modified_dirty_notes.update(reorder_result.modified_dirty_notes)
                sorted_cards_ids.extend(reorder_result.sorted_cards_ids)
                if not repositioning_required and reorder_result.repositioning_required == True:
                    repositioning_required = True

        # Reposition cards and apply changes
        if repositioning_required:
            with event_logger.add_benchmarked_entry("Reposition cards from targets."):
                col.sched.forgetCards(sorted_cards_ids)
                repositioning_anki_op_changes = col.sched.reposition_new_cards(
                    card_ids=sorted_cards_ids,
                    starting_from=0, step_size=1,
                    randomize=False, shift_existing=True
                )
        else:
            event_logger.add_entry("Order of cards from targets was already up-to-date!")

        # Update notes that have been modifies (field values for example)
        if (len(modified_dirty_notes) > 0):
            with event_logger.add_benchmarked_entry("Updating modified notes from targets."):
                update_notes_anki_op_changes = col.update_notes([note for note in modified_dirty_notes.values()])

        # Done
        event_logger.add_entry("Done with reordering of all targets!")
        return TargetListReorderResult(reorder_result_list=reorder_result_list, repositioning_anki_op_changes=repositioning_anki_op_changes, update_notes_anki_op_changes=update_notes_anki_op_changes)
