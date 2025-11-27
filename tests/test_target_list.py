from typing import TYPE_CHECKING
from frequencyman.configured_target import ConfiguredTargetDict, ValidConfiguredTarget
from frequencyman.target_list import JsonTargetsValidity, TargetList

if TYPE_CHECKING:
    from frequencyman.lib.utilities import JSON_TYPE

from tests.tools import MockCollection, MockCollectionFixture, with_test_collection, test_collection
col: MockCollectionFixture = test_collection

class TestTargetList:

    @with_test_collection("big_collection_es")
    def test_get_targets_from_json_valid_json(self, col: MockCollection):

        targets = TargetList.get_targets_from_json("""[
            {
                "id": "spanish_audio_only",
                "deck": "Spanish",
                "decks": ["Spanish"],
                "ranking_word_frequency": 0,
                "suspended_card_value": 0.1,
                "suspended_leech_card_value": 0.2,
                "ideal_word_count": [1, 10],
                "maturity_threshold": 0.5,
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
            id="spanish_audio_only",
            deck="Spanish",
            decks=["Spanish"],
            ranking_word_frequency=0.0, # type: ignore
            suspended_card_value=0.1,
            suspended_leech_card_value=0.2,
            ideal_word_count=[1, 10],
            maturity_threshold=0.5,
            notes=[
                {
                    "name": "-- My spanish --",
                    "fields": {
                        "Sentence": "ES"
                    }
                }
            ]
        )

    @with_test_collection("big_collection_es")
    def test_target_list_is_valid_query(self, col: MockCollection):

        assert TargetList.is_valid_query("deck:Spanish", col)
        assert TargetList.is_valid_query("-is:due", col)
        assert TargetList.is_valid_query("deck:\"Spanish\"", col)
        assert TargetList.is_valid_query("*", col)
        assert TargetList.is_valid_query("a", col)
        assert TargetList.is_valid_query("", col)
        assert TargetList.is_valid_query(" ", col)
        assert TargetList.is_valid_query(".", col)

        assert not TargetList.is_valid_query("deck:\"Spanish", col)
        assert not TargetList.is_valid_query("deck:Spanish)", col)
        assert not TargetList.is_valid_query(")", col)
        assert not TargetList.is_valid_query(":missing_pre", col)

    @with_test_collection("big_collection_es")
    def test_get_targets_from_json_invalid_json(self, col: MockCollection):

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

    @with_test_collection("big_collection_es")
    def test_get_targets_from_json_invalid_targets(self, col: MockCollection):

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
            '[{"deck": "not_a_deck", "notes": [{"name": "basic", "fields": {"Front": "EN"}}]}]': 'not_a_deck',
            '[{"scope_query": "\\"Spanish", "notes": [{"name": "basic", "fields": {"Front": "EN"}}]}]': 'not a valid query',
            '[{"deck": "Spanish", "reorder_scope_query": "\\"Spanish", "notes": [{"name": "basic", "fields": {"Front": "EN"}}]}]': 'not a valid query'
        }

        for index, (json_data, expected_error) in enumerate(invalid_targets_data.items()):
            targets_result = TargetList.get_targets_from_json(json_data, col, col.lang_data)
            assert targets_result.validity_state == JsonTargetsValidity.INVALID_TARGETS
            assert expected_error in targets_result.err_desc
            assert targets_result.valid_targets_defined is None
            if index >= 3:
                assert len(targets_result.targets_defined) == 1
            else:
                assert len(targets_result.targets_defined) == 0

    @with_test_collection("big_collection_es")
    def test_validate_target_list_preserves_key_order(self, col: MockCollection):

        # Define a target with a specific key order
        target_data: JSON_TYPE = {
            "deck": "Spanish",
            "notes": [
                {
                    "name": "Basic",
                    "fields": {
                        "Front": "ES"
                    }
                }
            ],
            "maturity_threshold": 0.5,
            "id": "test_order",
            "ideal_word_count": [1, 10]
        }

        # Create a list of targets
        targets_data: JSON_TYPE = [target_data]

        # Validate the target list
        (_, _, valid_target_list) = TargetList.validate_target_list(targets_data, col, col.lang_data)

        assert valid_target_list is not None
        assert len(valid_target_list) == 1

        valid_target = valid_target_list[0]

        # Check if keys are in the same order as in the input
        assert list(valid_target.keys()) == list(target_data.keys()) # type: ignore[union-attr]

        # The test above should test with an order that is non default
        assert list(valid_target.keys()) != list(ConfiguredTargetDict.__annotations__.keys())

