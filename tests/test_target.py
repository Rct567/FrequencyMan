from frequencyman.target import Target, ValidConfiguredTarget

from frequencyman.target import Target
from frequencyman.target_list import TargetList, TargetListReorderResult
from frequencyman.lib.event_logger import EventLogger
from frequencyman.language_data import LangDataId, LanguageData

from anki.collection import Collection, OpChanges, OpChangesWithCount

from anki.cards import CardId, Card
from anki.notes import Note, NoteId

class TestTarget:


    def test_construct_main_scope_query_deck(self):

        defined_target = ValidConfiguredTarget({
            'deck': 'big_collection_es',
            'notes': [{
                "name": "basic",
                "fields": {
                    "Front": "EN",
                    "Back": "ES"
                },
            }]
        })

        assert Target.construct_main_scope_query(defined_target) == '("deck:big_collection_es") AND ("note:basic")'

    def test_construct_main_scope_query_no_deck(self):

        defined_target = ValidConfiguredTarget({
            'notes': [{
                "name": "basic",
                "fields": {
                    "Front": "EN",
                    "Back": "ES"
                },
            }]
        })

        assert Target.construct_main_scope_query(defined_target) == '("note:basic")'

    def test_construct_main_scope_query_decks_string(self):

        defined_target = ValidConfiguredTarget({
            'decks': 'big_collection_es',
            'notes': [{
                "name": "basic",
                "fields": {
                    "Front": "EN",
                    "Back": "ES"
                },
            }]
        })

        assert Target.construct_main_scope_query(defined_target) == '("deck:big_collection_es") AND ("note:basic")'

    def test_construct_main_scope_query_decks_list(self):

        defined_target = ValidConfiguredTarget({
            'decks': ['big_collection_es', 'big_collection_it'],
            'notes': [{
                "name": "basic",
                "fields": {
                    "Front": "EN",
                    "Back": "ES"
                },
            }]
        })

        assert Target.construct_main_scope_query(defined_target) == '("deck:big_collection_es" OR "deck:big_collection_it") AND ("note:basic")'