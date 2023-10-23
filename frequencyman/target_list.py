import json
from typing import Tuple, TypedDict

ConfigTargetDataNotes = TypedDict('TargetDataNotes', {'name': str, 'fields': dict[str, str]})
ConfigTargetData = TypedDict('TargetData', {'deck': str, 'notes': list[ConfigTargetDataNotes]})

class Target:
    
    target:ConfigTargetData
    
    def __init__(self, target:ConfigTargetData) -> None:
        self.target = target
    
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
    
    def getNotes(self) -> dict[str, dict[str, str]]:
        return {note.get('name'): note.get('fields', {}) for note in self.target.get('notes', [])} 
    
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
    
    def __init__(self) -> None:
        self.target_list = []
    
    def __iter__(self):
        return iter(self.target_list)
    
    def load(self, target_list:list[ConfigTargetData]) -> int:
        is_valid = self.validate_list(target_list) == 1
        if (is_valid):
            self.target_list = [Target(target) for target in target_list]
        return is_valid
            
    def dump_json(self) -> str:
        target_list = [target.target for target in self.target_list]
        return json.dumps(target_list, indent=4)
        
    @staticmethod
    def validate_target(target:dict) -> int:
        if not isinstance(target, dict) or len(target.keys()) == 0:
            return 0
        for key in target.keys():
            if key not in ("deck", "notes"):
                return 0
        if not isinstance(target.get('notes'), list):
            return 0
        return 1
        
    @staticmethod
    def validate_list(target_data: list) -> int: 
        if len(target_data) < 1:
            return 0
        for target in target_data:
            result = TargetList.validate_target(target)
            if result == 0:
                return 0
        return 1 
    
    @staticmethod
    def handle_json(json_data: str) -> Tuple[int, list[ConfigTargetData]]:
        try:
            data:TargetList = json.loads(json_data)
            if isinstance(data, list):
                return (TargetList.validate_list(data), data)
            return (-1, [])
        except json.JSONDecodeError:
            return (-1, [])


    