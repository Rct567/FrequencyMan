from frequencyman.configured_target import ValidConfiguredTarget
from frequencyman.target_list import JsonTargetsResult, JsonTargetsValidity, TargetList, TargetListReorderResult
from frequencyman.language_data import LangDataId, LanguageData

from anki.collection import Collection, OpChanges, OpChangesWithCount

from anki.cards import CardId, Card
from anki.notes import Note, NoteId

from tests.tools import TestCollections

class TestTargetList:

    def test_get_targets_from_json_valid_json(self):

        col = TestCollections.get_test_collection('big_collection_es')

        targets = TargetList.get_targets_from_json("""[
            {
                "deck": "Spanish",
                "decks": ["Spanish"],
                "ranking_word_frequency": 0,
                "notes": [
                    {
                        "name": "-- My spanish --",
                        "fields": {
                            "Sentence": "ES"
                        }
                    }
                ]
            }
        ]""", col, col.lang_data)

        assert targets.err_desc == ""
        assert len(targets.targets_defined) == 1

        assert targets.valid_targets_defined is not None and len(targets.valid_targets_defined) == 1

        assert targets.valid_targets_defined[0] == ValidConfiguredTarget(
            deck="Spanish",
            decks=["Spanish"],
            ranking_word_frequency=0.0,
            notes=[
                {
                    "name": "-- My spanish --",
                    "fields": {
                        "Sentence": "ES"
                    }
                }
            ]
        )

    def test_get_targets_from_json_invalid_json(self):

        col = TestCollections.get_test_collection('big_collection_es')

        invalid_targets_data: list[str] = [
            "X",
            "{},}"
        ]

        for json_data in invalid_targets_data:
            targets = TargetList.get_targets_from_json(json_data, col, col.lang_data)
            assert targets.validity_state == JsonTargetsValidity.INVALID_JSON, json_data
            assert targets.err_desc != "", json_data
            assert targets.valid_targets_defined is None, json_data
            assert len(targets.targets_defined) == 0, json_data

    def test_get_targets_from_json_invalid_targets(self):

        col = TestCollections.get_test_collection('big_collection_es')

        invalid_targets_data: dict[str, str] = {
            '': '',
            '[]': 'list is empty',
            '{}': 'array expected',
            '[{}]': 'keys',
            '[{"deck": "Spanish"}]': 'notes',
            '[{"deck": "Spanish", "notes": []}]': 'empty',
            '[{"unknown_key":"", "deck":"Spanish"}]': 'unknown_key',
            '[{"deck": "Spanish", "notes": [{"name": "basic"}]}]': 'fields',
            '[{"deck": "Spanish", "notes": [{"name": "not_a_note_name", "fields": {"Front": "EN"}}]}]': 'not_a_note_name',
            '[{"deck": "Spanish", "notes": [{"name": "Basic", "fields": {"not_a_field_name": "EN"}}]}]': 'not_a_field_name',
            '[{"deck": "Spanish", "notes": [{"name": "basic", "fields": {"Front": "not_a_lang_data_id"}}]}]': 'not_a_lang_data_id',
            '[{"deck": "not_a_deck", "notes": [{"name": "basic", "fields": {"Front": "EN"}}]}]': 'not_a_deck'
        }

        for index, (json_data, expected_error) in enumerate(invalid_targets_data.items()):
            targets = TargetList.get_targets_from_json(json_data, col, col.lang_data)
            assert targets.validity_state == JsonTargetsValidity.INVALID_TARGETS, json_data
            assert expected_error in targets.err_desc, json_data
            assert targets.valid_targets_defined is None, json_data
            if index >= 3:
                assert len(targets.targets_defined) == 1, json_data
            else:
                assert len(targets.targets_defined) == 0, json_data
