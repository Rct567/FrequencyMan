

from frequencyman.configured_target import ValidConfiguredTarget
from frequencyman.language_data import LangDataId
from typing import get_args
from frequencyman.configured_target import ConfiguredTargetKeys, ConfiguredTargetDict


class TestConfiguredTarget:

    def test_construct_main_scope_query_deck(self):

        defined_target = ValidConfiguredTarget(
            deck='big_collection_es',
            notes=[{
                "name": "basic",
                "fields": {
                    "Front": "EN",
                    "Back": "ES"
                },
            }]
        )

        assert defined_target.construct_main_scope_query() == '("deck:big_collection_es") AND ("note:basic")'

    def test_construct_main_scope_query_no_deck(self):

        defined_target = ValidConfiguredTarget(
            notes=[{
                "name": "basic",
                "fields": {
                    "Front": "EN",
                    "Back": "ES"
                },
            }]
        )

        assert defined_target.construct_main_scope_query() == '("note:basic")'

    def test_construct_main_scope_query_decks_string(self):

        defined_target = ValidConfiguredTarget(
            decks='big_collection_es',
            notes=[{
                "name": "basic",
                "fields": {
                    "Front": "EN",
                    "Back": "ES"
                },
            }]
        )

        assert defined_target.construct_main_scope_query() == '("deck:big_collection_es") AND ("note:basic")'

    def test_construct_main_scope_query_decks_list(self):

        defined_target = ValidConfiguredTarget(
            decks=['big_collection_es', 'big_collection_it'],
            notes=[{
                "name": "basic",
                "fields": {
                    "Front": "EN",
                    "Back": "ES"
                },
            }]
        )

        assert defined_target.construct_main_scope_query() == '("deck:big_collection_es" OR "deck:big_collection_it") AND ("note:basic")'

    def test_get_language_data_ids_from_config_target(self):

        defined_target = ValidConfiguredTarget(
            notes=[{
                "name": "basic",
                "fields": {
                    "Front": "EN",
                    "Back": "es"
                },
            }]
        )

        assert defined_target.get_language_data_ids() == {LangDataId('en'), LangDataId('es')}

    def test_get_language_data_ids_from_config_target_same_languages(self):

        defined_target = ValidConfiguredTarget(
            notes=[{
                "name": "basic",
                "fields": {
                    "Front": "ES",
                    "Back": "es"
                },
            }]
        )

        assert defined_target.get_language_data_ids() == {LangDataId('es')}

    def test_get_config_fields_per_note_type(self):

        defined_target = ValidConfiguredTarget(
            deck='big_collection_es',
            notes=[{
                "name": "basic",
                "fields": {
                    "Front": "EN",
                    "Back": "es"
                },
            }]
        )

        assert defined_target.get_config_fields_per_note_type() == {
            "basic": {
                "Front": LangDataId("en"),
                "Back": LangDataId("es")
            }
        }

    def test_get_reorder_scope_query_none(self):

        defined_target = ValidConfiguredTarget(
            deck='big_collection_es',
            notes=[{
                "name": "basic",
                "fields": {
                    "Front": "EN",
                    "Back": "es"
                },
            }]
        )

        assert defined_target.get_reorder_scope_query() is None

    def test_get_reorder_scope_query(self):

        defined_target = ValidConfiguredTarget(
            deck='big_collection_es',
            reorder_scope_query='-card:*Reading*',
            notes=[{
                "name": "basic",
                "fields": {
                    "Front": "EN",
                    "Back": "es"
                },
            }]
        )

        reorder_scope = defined_target.get_reorder_scope_query()
        assert reorder_scope == '("deck:big_collection_es") AND ("note:basic") AND (-card:*Reading*)'
        assert defined_target.construct_main_scope_query() in reorder_scope

    def test_configured_target_keys_matches_dict_annotations(self):

        # Get keys from the Literal type
        literal_keys = set(get_args(ConfiguredTargetKeys))

        # Get keys from the TypedDict annotations
        typeddict_keys = set(ConfiguredTargetDict.__annotations__.keys())

        # They should match exactly
        assert literal_keys == typeddict_keys, (
            f"ConfiguredTargetKeys Literal is out of sync with ConfiguredTargetDict!\n"
            f"Missing in Literal: {typeddict_keys - literal_keys}\n"
            f"Extra in Literal: {literal_keys - typeddict_keys}"
        )

        # All TypedDict annotations must be in 'valid keys'
        assert all(annotation_key in ValidConfiguredTarget.get_valid_keys() for annotation_key in ConfiguredTargetDict.__annotations__.keys())

