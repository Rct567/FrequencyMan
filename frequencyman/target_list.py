import json
from typing import Optional, Sequence, Tuple

from anki.collection import Collection, OpChanges, OpChangesWithCount
from anki.cards import CardId, Card

from .target import ConfigTargetData, ReorderResult, Target
from .word_frequency_list import WordFrequencyLists
from .lib.event_logger import EventLogger


class TargetList:

    target_list: list[Target]
    word_frequency_lists: WordFrequencyLists

    def __init__(self, word_frequency_lists: WordFrequencyLists) -> None:
        self.target_list = []
        self.word_frequency_lists = word_frequency_lists

    def __iter__(self):
        return iter(self.target_list)

    def __len__(self):
        return len(self.target_list)

    def set_targets(self, target_list: list[ConfigTargetData]) -> int:
        (validity_state, _) = self.validate_list(target_list)
        if (validity_state == 1):
            self.target_list = [Target(target, target_num) for target_num, target in enumerate(target_list)]
        return validity_state

    def has_targets(self) -> bool:
        return len(self.target_list) > 0

    def dump_json(self) -> str:
        target_list = [target.target for target in self.target_list]
        return json.dumps(target_list, indent=4)

    def validate_target(self, target: dict) -> Tuple[int, str]:
        if not isinstance(target, dict) or len(target.keys()) == 0:
            return (0, "Target is missing keys or is not a valid type (object expected). ")
        for key in target.keys():
            if key not in ("deck", "decks", "notes", "scope_query"):
                return (0, f"Target has unknown key '{key}'.")
        # check field value for notes
        if 'notes' not in target.keys():
            return (0, "Target object is missing key 'notes'.")
        elif not isinstance(target.get('notes'), list):
            return (0, "Target object value for 'notes' is not a valid type (array expected).")
        elif len(target.get('notes', [])) == 0:
            return (0, "Target object value for 'notes' is empty.")

        for note in target.get('notes', []):
            if not isinstance(note, dict):
                return (0, "Note specified in target.notes is not a valid type (object expected).")
            if "name" not in note:
                return (0, "Note object specified in target.notes is missing key 'name'.")
            if "fields" not in note:
                return (0, "Note object specified in target.notes is is missing key 'fields'.")

            for lang_key in note.get('fields', {}).values():
                if not self.word_frequency_lists.key_has_frequency_list_file(lang_key):
                    return (0, "No word frequency list file found for key '{}'!".format(lang_key))

        return (1, "")

    def validate_list(self, target_data: list) -> Tuple[int, str]:
        if not isinstance(target_data, list):
            return (0, "Reorder target is not a valid type (array expected)")
        elif len(target_data) < 1:
            return (0, "Reorder target is an empty array.")
        for target in target_data:
            (validity_state, err_desc) = self.validate_target(target)
            if validity_state == 0:
                return (0, err_desc)
        return (1, "")

    def handle_json(self, json_data: str) -> Tuple[int, list[ConfigTargetData], str]:
        try:
            data: TargetList = json.loads(json_data)
            if isinstance(data, list):
                (validity_state, err_desc) = self.validate_list(data)
                return (validity_state, data, err_desc)
            return (-1, [], "Not a list!")
        except json.JSONDecodeError:
            return (-1, [], "Invalid JSON!")

    def reorder_cards(self, col: Collection, event_logger: EventLogger) -> list[ReorderResult]:

        reorder_result_list: list[ReorderResult] = []
        sorted_cards_ids: list[CardId] = []
        repositioning_required = False

        for target in self.target_list:
            with event_logger.add_benchmarked_entry(f"Reordering target #{target.index_num}."):
                reorder_result = target.reorder_cards(self.word_frequency_lists, col, event_logger)
                reorder_result_list.append(reorder_result)
                sorted_cards_ids.extend(reorder_result.sorted_cards_ids)
                if not repositioning_required and reorder_result.repositioning_required == True:
                    repositioning_required = True

        # Reposition cards and apply changes
        if repositioning_required:
            with event_logger.add_benchmarked_entry("Reposition cards from targets."):
                col.sched.forgetCards(sorted_cards_ids)
                col.sched.reposition_new_cards(
                    card_ids=sorted_cards_ids,
                    starting_from=0, step_size=1,
                    randomize=False, shift_existing=True
                )
        else:
            event_logger.add_entry("Order of cards from targets was already up-to-date!")

        event_logger.add_entry("Done with reordering of all targets!")

        return reorder_result_list
