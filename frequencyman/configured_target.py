"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

import re
from typing import Any, Literal, Optional, TypedDict, Union, overload
from typing_extensions import Unpack
from collections.abc import Sequence, KeysView

from .language_data import LangDataId
from .lib.utilities import JSON_TYPE, override
from .card_ranker import CardRanker


class ConfiguredTargetNote(TypedDict):
    name: str
    fields: dict[str, str]


ConfiguredTargetKeys = Literal[
    'id',
    'deck',
    'decks',
    'scope_query',
    'reorder_scope_query',
    'familiarity_sweetspot_point',
    'maturity_threshold',
    'maturity_min_num_cards',
    'maturity_min_num_notes',
    'suspended_card_value',
    'suspended_leech_card_value',
    'ideal_word_count',
    'ranking_factors',
    'corpus_segmentation_strategy',
    'notes'
]


class ConfiguredTargetDict(TypedDict, total=False):
    id: str
    deck: str
    decks: Union[str, list[str]]
    scope_query: str
    reorder_scope_query: str
    familiarity_sweetspot_point: Union[float, str]
    maturity_threshold: float
    maturity_min_num_cards: int
    maturity_min_num_notes: int
    suspended_card_value: float
    suspended_leech_card_value: float
    ideal_word_count: tuple[int, int]
    ranking_factors: dict[str, float]
    corpus_segmentation_strategy: str
    notes: list[ConfiguredTargetNote]


class ValidConfiguredTarget(dict):

    def __init__(self, **kwargs: Unpack[ConfiguredTargetDict]) -> None:
        super().__init__(kwargs)

    @overload
    def __getitem__(self, key: Literal['id', 'deck', 'scope_query', 'reorder_scope_query', 'corpus_segmentation_strategy']) -> str:
        ...

    @overload
    def __getitem__(self, key: Literal['decks']) -> Union[str, list[str]]:
        ...

    @overload
    def __getitem__(self, key: Literal['familiarity_sweetspot_point']) -> Union[float, str]:
        ...

    @overload
    def __getitem__(self, key: Literal['maturity_threshold', 'suspended_card_value', 'suspended_leech_card_value']) -> float:
        ...

    @overload
    def __getitem__(self, key: Literal['maturity_min_num_cards', 'maturity_min_num_notes']) -> int:
        ...

    @overload
    def __getitem__(self, key: Literal['ideal_word_count']) -> tuple[int, int]:
        ...

    @overload
    def __getitem__(self, key: Literal['ranking_factors']) -> dict[str, float]:
        ...

    @overload
    def __getitem__(self, key: Literal['notes']) -> list[ConfiguredTargetNote]:
        ...

    @override
    def __getitem__(self, key: ConfiguredTargetKeys):
        return super().__getitem__(key)

    @overload
    def __setitem__(self, key: Literal['id', 'deck', 'scope_query', 'reorder_scope_query', 'corpus_segmentation_strategy'], value: str) -> None:
        ...

    @overload
    def __setitem__(self, key: Literal['decks'], value: Union[str, list[str]]) -> None:
        ...

    @overload
    def __setitem__(self, key: Literal['familiarity_sweetspot_point'], value: Union[float, str]) -> None:
        ...

    @overload
    def __setitem__(self, key: Literal['maturity_threshold', 'suspended_card_value', 'suspended_leech_card_value'], value: float) -> None:
        ...

    @overload
    def __setitem__(self, key: Literal['maturity_min_num_cards', 'maturity_min_num_notes'], value: int) -> None:
        ...

    @overload
    def __setitem__(self, key: Literal['ideal_word_count'], value: tuple[int, int]) -> None:
        ...

    @overload
    def __setitem__(self, key: Literal['ranking_factors'], value: dict[str, float]) -> None:
        ...

    @overload
    def __setitem__(self, key: Literal['notes'], value: list[ConfiguredTargetNote]) -> None:
        ...

    @override
    def __setitem__(self, key: ConfiguredTargetKeys, value: Union[str, float, list, tuple[int, int], dict]) -> None:
        return super().__setitem__(key, value)

    def set_custom_ranking_weight(self, key: str, value: float) -> None:
        assert key.startswith('ranking_')
        return super().__setitem__(key, value)

    @staticmethod
    def get_valid_keys() -> set[str]:

        valid_keys = set(ConfiguredTargetDict.__annotations__.keys())
        assert len(valid_keys) > 0 and all(isinstance(key, str) for key in valid_keys)

        for rankin_factor in CardRanker.get_default_ranking_factors_span().keys():
            valid_keys.add('ranking_'+rankin_factor)
        return valid_keys

    def __getattr__(self, name: str):
        raise AttributeError(f"Access to attribute '{name}' is not allowed")

    @override
    def __setattr__(self, name: str, value: Any):
        raise AttributeError(f"Setting attribute '{name}' is not allowed")

    def get_config_fields_per_note_type(self) -> dict[str, dict[str, LangDataId]]:

        config_notes = {}

        for note in self['notes']:
            note_fields = {field_name: LangDataId(lang_data_id.lower()) for field_name, lang_data_id in note['fields'].items()}
            config_notes[note['name']] = note_fields

        return config_notes

    def get_language_data_ids(self) -> set[LangDataId]:

        keys = set()
        for note in self['notes']:
            for lang_data_id in note['fields'].values():
                keys.add(LangDataId(lang_data_id.lower()))
        return keys

    def construct_main_scope_query(self) -> str:

        target_notes = self["notes"] if isinstance(self["notes"], list) else []
        note_queries = ['"note:'+note_type['name']+'"' for note_type in target_notes if isinstance(note_type['name'], str)]

        if len(note_queries) < 1:
            return ''

        notes_query = "(" + " OR ".join(note_queries) + ")"

        defined_scope_query = JsonConfiguredTarget(self).get_query_from_defined_main_scope()

        if defined_scope_query is None:
            return notes_query  # main scope is just the notes

        return defined_scope_query+" AND "+notes_query

    def get_reorder_scope_query(self) -> Optional[str]:

        if 'reorder_scope_query' in self and len(self['reorder_scope_query']) > 0:
            return self.construct_main_scope_query()+" AND ("+self['reorder_scope_query']+")"



class JsonConfiguredTarget:

    data: dict[str, JSON_TYPE]

    def __init__(self, data: dict[str, JSON_TYPE]) -> None:
        self.data = data

    def get_query_from_defined_main_scope(self) -> Optional[str]:

        scope_query = self.get('scope_query')

        scope_queries: list[str] = []

        # defined decks

        decks = self.get_deck_names()

        for deck_name in decks:
            if len(deck_name.strip()) > 0:
                scope_queries.append('"deck:' + deck_name + '"')

        # defined scope query

        if scope_query is not None and isinstance(scope_query, str) and len(scope_query.strip()) > 0:
            scope_queries.append(scope_query)

        # result
        if len(scope_queries) > 0:
            scope_query_result = " OR ".join(scope_queries)
            return "("+scope_query_result+")"

        return None

    def get_deck_names(self) -> Sequence[str]:

        defined_deck = self.data.get('deck', None)
        defined_decks = self.data.get('decks', None)

        decks: list[str] = []

        if defined_deck is not None and isinstance(defined_deck, str) and len(defined_deck) > 0:
            decks.append(defined_deck)

        if defined_decks is not None and isinstance(defined_decks, list) and len(defined_decks) > 0:
            decks.extend(deck_name for deck_name in defined_decks if isinstance(deck_name, str) and len(deck_name) > 0)
        if defined_decks is not None and isinstance(defined_decks, str) and len(defined_decks) > 0:
            decks.extend(deck_name.replace('\\,', ',').strip() for deck_name in re.split(r'(?<!\\),', defined_decks) if isinstance(deck_name, str))

        return decks

    def rename_property(self, old_key: str, new_key: str) -> None:

        if old_key in self.data:
            # rename while preserving order
            self.data = {(new_key if k == old_key else k): v for k, v in self.data.items()}

    def rename_properties(self, renamed_properties: dict[str, str]) -> None:

        for old_key, new_key in renamed_properties.items():
            self.rename_property(old_key, new_key)

    def rename_ranking_factors(self, renamed_ranking_factors: dict[str, str]) -> None:

        for old_factor_name, new_factor_name in renamed_ranking_factors.items():
            self.rename_property('ranking_'+old_factor_name, 'ranking_'+new_factor_name)

        if 'ranking_factors' in self.data and isinstance(self.data['ranking_factors'], dict) and len(self.data['ranking_factors']) > 0:
            for old_factor_name, new_factor_name in renamed_ranking_factors.items():
                if old_factor_name in self.data['ranking_factors']:
                    self.data['ranking_factors'][new_factor_name] = self.data['ranking_factors'][old_factor_name]
                    del self.data['ranking_factors'][old_factor_name]

    def get(self, key: str) -> Any:
        return self.data.get(key)

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def __contains__(self, key: str) -> bool:
        return key in self.data

    def keys(self) -> KeysView[str]:
        return self.data.keys()
