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

from .card_ranker import CardRanker
from .target import ConfigTargetData, TargetReorderResult, Target, ConfigTargetDataNote
from .target_cards import TargetCards
from .word_frequency_list import WordFrequencyLists
from .lib.event_logger import EventLogger


@dataclass(frozen=True)
class TargetListReorderResult():
    reorder_result_list: list[TargetReorderResult]
    update_notes_anki_op_changes: Optional[OpChanges]
    modified_dirty_notes: dict[NoteId, Optional[Note]]
    num_cards_repositioned: int


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
            self.target_list = [Target(target, target_num, self.col) for target_num, target in enumerate(target_list)]
        return (validity_state, err_desc)

    def has_targets(self) -> bool:
        return len(self.target_list) > 0

    def dump_json(self) -> str:
        target_list = [target.config_target for target in self.target_list]
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
            known_keys = {"deck", "decks", "notes", "scope_query", "reorder_scope_query", "familiarity_sweetspot_point"}
            known_keys.update(map(lambda s: "ranking_"+s, CardRanker.get_default_ranking_factors_span().keys()))
            if key not in known_keys:
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

            note_model = self.col.models.by_name(note['name'])

            if not note_model:
                return (0, "Name '{}' for note object specified in target[{}].notes does not exist.".format(note['name'], index))

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

    def get_validated_data_from_json(self, json_data: str) -> tuple[int, list[ConfigTargetData], str]:

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
        modified_dirty_notes: dict[NoteId, Optional[Note]] = {}
        num_cards_repositioned = 0

        # Reposition cards for each target
        for target in self.target_list:
            with event_logger.add_benchmarked_entry("Reordering target #{}.".format(target.index_num)):
                reorder_result = target.reorder_cards(num_cards_repositioned+1, self.word_frequency_lists, event_logger, modified_dirty_notes)
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

        # Clear cache
        Target.corpus_cache = {}
        Target.target_cards_cache = {}
        TargetCards.notes_from_cards_cached = {}

        # Done
        event_logger.add_entry("Done with reordering of all targets! {:n} cards repositioned.".format(num_cards_repositioned))
        return TargetListReorderResult(
            num_cards_repositioned=num_cards_repositioned,
            reorder_result_list=reorder_result_list,
            update_notes_anki_op_changes=update_notes_anki_op_changes,
            modified_dirty_notes=modified_dirty_notes
        )
