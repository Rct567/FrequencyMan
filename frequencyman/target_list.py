import json
from typing import Tuple, TypedDict

from .word_frequency_list import WordFrequencyLists

ConfigTargetDataNotes = TypedDict('TargetDataNotes', {'name': str, 'fields': dict[str, str]})
ConfigTargetData = TypedDict('TargetData', {'deck': str, 'notes': list[ConfigTargetDataNotes]})

class Target:
    
    target:ConfigTargetData
    index_num:int
    
    def __init__(self, target:ConfigTargetData, index_num:int) -> None:
        self.target = target
        self.index_num = index_num
    
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
    
    def get_notes_language_keys(self) -> list[str]:
        keys = []
        for note in self.target.get('notes', []):
            for lang_key in note['fields'].values():
                keys.append(lang_key.lower())
        return keys   
        
    
    def construct_search_query(self) -> str:
        target_notes = self.get("notes", []) if isinstance(self.get("notes"), list) else []
        note_queries = ['"note:'+note_type['name']+'"' for note_type in target_notes if isinstance(note_type['name'], str)]
        
        if len(note_queries) < 1:
            return ''

        search_query = "(" + " OR ".join(note_queries) + ")";
        
        if "deck" in self: 
            if isinstance(self.get("deck"), str) and len(self.get("deck", '')) > 0:
                target_decks = [self.get("deck", '')]
            elif isinstance(self.get("deck"), list):
                target_decks = [deck_name for deck_name in self.get("deck", []) if isinstance(deck_name, str) and len(deck_name) > 0]
            else: 
                target_decks = []
                
            if len(target_decks) > 0:
                deck_queries = ['"deck:' + deck_name + '"' for deck_name in target_decks if len(deck_name) > 0]
                target_decks_query = " OR ".join(deck_queries)
                search_query = "("+target_decks_query+")" + search_query
        
        return search_query

class TargetList:
    
    target_list:list[Target]
    word_frequency_lists:WordFrequencyLists
    
    
    def __init__(self, word_frequency_lists:WordFrequencyLists) -> None:
        self.target_list = []
        self.word_frequency_lists = word_frequency_lists
    
    def __iter__(self):
        return iter(self.target_list)
    
    def __len__(self):
        return len(self.target_list)
    
    def set_targets(self, target_list:list[ConfigTargetData]) -> int:
        (validity_state, _) = self.validate_list(target_list)
        if (validity_state == 1):
            self.target_list = [Target(target, target_num) for target_num, target in enumerate(target_list)]
        return validity_state
    
    def has_targets(self) -> bool:
        return len(self.target_list) > 0
            
    def dump_json(self) -> str:
        target_list = [target.target for target in self.target_list]
        return json.dumps(target_list, indent=4)
        
    def validate_target(self, target:dict) -> Tuple[int, str]:
        if not isinstance(target, dict) or len(target.keys()) == 0:
            return (0, "Target is missing keys or is not a valid type (object expected). ")
        for key in target.keys():
            if key not in ("deck", "notes"):
                return (0, f"Target has invalid key '{key}'.")
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
            data:TargetList = json.loads(json_data)
            if isinstance(data, list):
                (validity_state, err_desc) = self.validate_list(data)
                return (validity_state, data, err_desc)
            return (-1, [], "Not a list!")
        except json.JSONDecodeError:
            return (-1, [], "Invalid JSON!")


    