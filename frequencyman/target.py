from dataclasses import dataclass
from typing import Optional, Sequence, Tuple, TypedDict

from aqt import QAction
from aqt.qt import *
from aqt.main import AnkiQt

from anki.collection import Collection
from anki.cards import CardId, Card

ConfigTargetDataNotes = TypedDict('TargetDataNotes', {'name': str, 'fields': dict[str, str]})
ConfigTargetData = TypedDict('TargetData', {'deck': str, 'notes': list[ConfigTargetDataNotes]})

@dataclass
class TargetResult:
    all_cards_ids:Sequence[CardId]
    all_cards:list[Card]
    new_cards:list[Card]
    new_cards_ids:Sequence[CardId]
    

class Target:
    
    target:ConfigTargetData
    index_num:int
    query:Optional[str]
    result:Optional[TargetResult]

    def __init__(self, target:ConfigTargetData, index_num:int) -> None:
        self.target = target
        self.index_num = index_num
        self.query = None
        self.result = None
    
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
    
    def get_search_query(self) -> str:
        if (self.query is None):
            self.query = self.construct_search_query()
        return self.query
    
    def get_cards(self, col:Collection):
        
        all_cards_ids = col.find_cards(self.get_search_query(), order="c.due asc")
        all_cards = [col.get_card(card_id) for card_id in all_cards_ids]
        new_cards = [card for card in all_cards if card.queue == 0]
        new_cards_ids:Sequence[CardId] = [card.id for card in new_cards] 
        return TargetResult(all_cards_ids, all_cards, new_cards, new_cards_ids)
    
    
