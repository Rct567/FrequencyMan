from typing import Any
from typing_extensions import Unpack

from frequencyman.target import Target
from frequencyman.target_cards import TargetCards
from frequencyman.configured_target import ConfiguredTargetDict, ValidConfiguredTarget
from frequencyman.target_corpus_data import CorpusSegmentationStrategy

from tests.tools import (
    MockCollection,
    with_test_collection,
    test_collection as test_collection_fixture
)

col = test_collection_fixture

class TestTarget:

    def _create_target(self, col: MockCollection, **kwargs: Unpack[ConfiguredTargetDict]):
        config_kwargs: dict[str, Any] = {
            "deck": "Default",
            "notes": [],
        }
        config_kwargs.update(kwargs)

        config_target = ValidConfiguredTarget(**config_kwargs)

        target = Target(
            config_target=config_target,
            index_num=0,
            col=col,
            language_data=col.lang_data,
            cacher=col.cacher
        )
        return config_target, target


    @with_test_collection("empty_collection")
    def test_get_corpus_data_non_cached_config(self, col: MockCollection):
        # Setup
        _, target = self._create_target(
            col,
            maturity_threshold=0.8,
            maturity_min_num_cards=5,
            maturity_min_num_notes=3,
            familiarity_sweetspot_point=0.5,
            suspended_card_value=0.1,
            suspended_leech_card_value=0.05,
            corpus_segmentation_strategy="by_note_model_id_and_field_name"
        )

        # Create dummy TargetCards (can be empty for this test as we focus on config propagation)
        target_cards = TargetCards([], col)

        # Execute
        corpus_data = target.get_corpus_data_non_cached(target_cards)

        # Assert
        assert corpus_data.maturity_requirements.threshold == 0.8
        assert corpus_data.maturity_requirements.min_num_cards == 5
        assert corpus_data.maturity_requirements.min_num_notes == 3
        assert corpus_data.familiarity_sweetspot_point == 0.5
        assert corpus_data.suspended_card_value == 0.1
        assert corpus_data.suspended_leech_card_value == 0.05
        assert corpus_data.segmentation_strategy == CorpusSegmentationStrategy.BY_NOTE_MODEL_ID_AND_FIELD_NAME


    @with_test_collection("empty_collection")
    def test_get_corpus_data_partial_maturity_config(self, col: MockCollection):
        # Setup with only one maturity setting
        _, target = self._create_target(
            col,
            maturity_min_num_cards=5
        )

        target_cards = TargetCards([], col)

        # Execute
        corpus_data = target.get_corpus_data_non_cached(target_cards)

        # Assert
        assert corpus_data.maturity_requirements.threshold == 0.28 # threshold should be default
        assert corpus_data.maturity_requirements.min_num_cards == 5 # min_num_cards should be updated
        assert corpus_data.maturity_requirements.min_num_notes == 1 # min_num_notes should be default


    @with_test_collection("empty_collection")
    def test_get_corpus_data_updates_on_config_change(self, col: MockCollection):
        # Setup
        config_target, target = self._create_target(
            col,
            familiarity_sweetspot_point=0.5
        )

        # Initialize cache_data
        target.cache_data = {'target_cards': {}, 'corpus': {}}

        target_cards = TargetCards([], col)

        # First call
        corpus_data_1 = target.get_corpus_data(target_cards)
        assert corpus_data_1.familiarity_sweetspot_point == 0.5

        # Change configuration
        config_target['familiarity_sweetspot_point'] = 0.8

        # Execute again
        corpus_data_2 = target.get_corpus_data(target_cards)

        # Assert
        assert corpus_data_2.familiarity_sweetspot_point == 0.8
        assert corpus_data_1 is not corpus_data_2

    @with_test_collection("empty_collection")
    def test_get_corpus_data_none_cached_updates_on_config_change(self, col: MockCollection):
        # Setup
        config_target, target = self._create_target(
            col,
            familiarity_sweetspot_point=0.5
        )

        # Initialize cache_data
        target.cache_data = {'target_cards': {}, 'corpus': {}}

        target_cards = TargetCards([], col)

        # First call
        corpus_data_1 = target.get_corpus_data_non_cached(target_cards)
        assert corpus_data_1.familiarity_sweetspot_point == 0.5

        # Change configuration
        config_target['familiarity_sweetspot_point'] = 0.8

        # Execute again
        corpus_data_2 = target.get_corpus_data(target_cards)

        # Assert
        assert corpus_data_2.familiarity_sweetspot_point == 0.8
        assert corpus_data_1 is not corpus_data_2

