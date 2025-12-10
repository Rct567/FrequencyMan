"""
Tests for ReorderCardsTab.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from tests.tools import (
    reorder_logger as reorder_logger_fixture,
    test_collection as test_collection_fixture,
    with_test_collection,
)

from tests.ui.common import (
    MockAnkiQt,
    build_loaded_config,
    setup_mock_main_window,
    frequencyman_window_creator,
    ReorderCardsTab
)

if TYPE_CHECKING:
    import pytest
    from anki.collection import Collection
    from pytestqt.qtbot import QtBot
    from frequencyman.reorder_logger import ReorderLogger


reorder_logger = reorder_logger_fixture
test_collection = test_collection_fixture


class TestReorderCardsTab:

    @with_test_collection("two_deck_collection")
    def test_reorder_cards_buttons_on_non_existing_target_list(
        self,
        qtbot: QtBot,
        test_collection: Collection,
        reorder_logger: ReorderLogger,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:

        setup_mock_main_window(monkeypatch)

        addon_config = build_loaded_config([], set_defaults=False)

        mw = MockAnkiQt(test_collection)
        qtbot.addWidget(mw)

        fm_window = frequencyman_window_creator(mw, addon_config, reorder_logger)
        assert fm_window
        qtbot.addWidget(fm_window)
        qtbot.waitExposed(fm_window)

        reorder_tab = fm_window.tab_menu_options["reorder_cards"]

        assert fm_window.tab_widget.currentWidget() == reorder_tab
        assert isinstance(reorder_tab, ReorderCardsTab)

        # Wait for paint event to occur
        qtbot.waitUntil(lambda: reorder_tab.first_paint_event_done, timeout=5_000)
        qtbot.waitUntil(lambda: reorder_tab.targets_input_textarea.json_result is not None, timeout=5_000)

        assert reorder_tab.targets_input_textarea.json_result
        assert "not yet defined" in reorder_tab.targets_input_textarea.json_result.err_desc
        assert len(reorder_tab.targets_input_textarea.json_result.targets_defined) == 0
        assert not reorder_tab.targets_input_textarea.json_result.valid_targets_defined
        assert not reorder_tab.target_list.has_targets()

        # check buttons
        assert not reorder_tab.reorder_button.isEnabled()
        assert not reorder_tab.save_button.isEnabled()
        assert not reorder_tab.restore_button.isVisible()
        assert not reorder_tab.reset_button.isEnabled()

        # done
        fm_window.close()
        qtbot.waitUntil(lambda: not fm_window.isVisible(), timeout=5_000)
        mw.close()

    @with_test_collection("two_deck_collection")
    def test_reorder_cards_buttons_on_empty_target_list(
        self,
        qtbot: QtBot,
        test_collection: Collection,
        reorder_logger: ReorderLogger,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:

        setup_mock_main_window(monkeypatch)

        addon_config = build_loaded_config([], set_defaults=False)

        addon_config.update_setting('reorder_target_list', []) # no target in list

        mw = MockAnkiQt(test_collection)
        qtbot.addWidget(mw)

        fm_window = frequencyman_window_creator(mw, addon_config, reorder_logger)
        assert fm_window
        qtbot.addWidget(fm_window)
        qtbot.waitExposed(fm_window)

        reorder_tab = fm_window.tab_menu_options["reorder_cards"]

        assert fm_window.tab_widget.currentWidget() == reorder_tab
        assert isinstance(reorder_tab, ReorderCardsTab)

        # Wait for paint event to occur
        qtbot.waitUntil(lambda: reorder_tab.first_paint_event_done, timeout=5_000)
        qtbot.waitUntil(lambda: reorder_tab.targets_input_textarea.json_result is not None, timeout=5_000)

        assert reorder_tab.targets_input_textarea.json_result
        assert "not yet defined" in reorder_tab.targets_input_textarea.json_result.err_desc
        assert len(reorder_tab.targets_input_textarea.json_result.targets_defined) == 0
        assert not reorder_tab.targets_input_textarea.json_result.valid_targets_defined
        assert not reorder_tab.target_list.has_targets()

        # check buttons
        assert not reorder_tab.reorder_button.isEnabled()
        assert not reorder_tab.save_button.isEnabled()
        assert not reorder_tab.restore_button.isVisible()
        assert not reorder_tab.reset_button.isEnabled()

        # done
        fm_window.close()
        qtbot.waitUntil(lambda: not fm_window.isVisible(), timeout=5_000)
        mw.close()


    @with_test_collection("two_deck_collection")
    def test_reorder_cards_buttons_on_target_list_with_empty_target(
        self,
        qtbot: QtBot,
        test_collection: Collection,
        reorder_logger: ReorderLogger,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:

        setup_mock_main_window(monkeypatch)

        addon_config = build_loaded_config([])

        addon_config.update_setting('reorder_target_list', [{}]) # no target in list

        mw = MockAnkiQt(test_collection)
        qtbot.addWidget(mw)

        fm_window = frequencyman_window_creator(mw, addon_config, reorder_logger)
        assert fm_window
        qtbot.addWidget(fm_window)
        qtbot.waitExposed(fm_window)

        reorder_tab = fm_window.tab_menu_options["reorder_cards"]

        assert fm_window.tab_widget.currentWidget() == reorder_tab
        assert isinstance(reorder_tab, ReorderCardsTab)

        # Wait for paint event to occur
        qtbot.waitUntil(lambda: reorder_tab.first_paint_event_done, timeout=5_000)
        qtbot.waitUntil(lambda: reorder_tab.targets_input_textarea.json_result is not None, timeout=5_000)

        assert reorder_tab.targets_input_textarea.json_result
        assert "does not have any keys" in reorder_tab.targets_input_textarea.json_result.err_desc
        assert len(reorder_tab.targets_input_textarea.json_result.targets_defined) == 1
        assert not reorder_tab.targets_input_textarea.json_result.valid_targets_defined
        assert not reorder_tab.target_list.has_targets()

        # check buttons
        assert not reorder_tab.reorder_button.isEnabled()
        assert not reorder_tab.save_button.isEnabled()
        assert not reorder_tab.restore_button.isVisible()
        assert not reorder_tab.reset_button.isEnabled()

        # done
        fm_window.forceClose() # prevent prompt, since changes have been made
        qtbot.waitUntil(lambda: not fm_window.isVisible(), timeout=5_000)
        mw.close()


    @with_test_collection("two_deck_collection")
    def test_reorder_cards_buttons_on_target_list_changed(
        self,
        qtbot: QtBot,
        test_collection: Collection,
        reorder_logger: ReorderLogger,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:

        setup_mock_main_window(monkeypatch)

        addon_config = build_loaded_config([])

        addon_config.update_setting('reorder_target_list', [
            {
                'deck': 'decka',
                'notes': [{
                    "name": "Basic",
                    "fields": {
                        "Front": "EN",
                        "Back": "ES"
                    },
                }]
            }
        ])

        mw = MockAnkiQt(test_collection)
        qtbot.addWidget(mw)

        fm_window = frequencyman_window_creator(mw, addon_config, reorder_logger)
        assert fm_window
        qtbot.addWidget(fm_window)
        qtbot.waitExposed(fm_window)

        reorder_tab = fm_window.tab_menu_options["reorder_cards"]

        assert fm_window.tab_widget.currentWidget() == reorder_tab
        assert isinstance(reorder_tab, ReorderCardsTab)

        # Wait for paint event to occur
        qtbot.waitUntil(lambda: reorder_tab.first_paint_event_done, timeout=5_000)
        qtbot.waitUntil(lambda: reorder_tab.targets_input_textarea.json_result is not None, timeout=5_000)

        # one valid target
        assert reorder_tab.targets_input_textarea.json_result
        assert reorder_tab.targets_input_textarea.json_result.err_desc == ""
        assert len(reorder_tab.targets_input_textarea.json_result.targets_defined) == 1
        assert reorder_tab.targets_input_textarea.json_result.valid_targets_defined
        assert len(reorder_tab.targets_input_textarea.json_result.valid_targets_defined) == 1
        assert reorder_tab.target_list.has_targets()

        # check buttons
        assert reorder_tab.reorder_button.isEnabled()
        assert not reorder_tab.save_button.isEnabled()
        assert not reorder_tab.restore_button.isVisible()
        assert not reorder_tab.reset_button.isEnabled()

        # change to invalid target list
        reorder_tab.targets_input_textarea.setText("[{}]")

        # check buttons again
        assert not reorder_tab.reorder_button.isEnabled()
        assert not reorder_tab.save_button.isEnabled()
        assert reorder_tab.restore_button.isVisible()
        assert reorder_tab.reset_button.isEnabled()

        # change to target with legacy properties

        valid_target_definition = """
             [ {
                "deck": "decka",
                "focus_words_max_familiarity": 1,
                "ranking_reinforce_focus_words": 1,
                "notes": [{
                    "name": "Basic",
                    "fields": {
                        "Front": "EN",
                        "Back": "ES"
                    },
                }]
            }]
        """

        reorder_tab.targets_input_textarea.setText(valid_target_definition)

        # should be oke
        assert reorder_tab.targets_input_textarea.json_result
        assert reorder_tab.targets_input_textarea.json_result.err_desc == ""
        assert reorder_tab.reorder_button.isEnabled()
        assert reorder_tab.save_button.isEnabled()
        assert not reorder_tab.restore_button.isVisible()
        assert reorder_tab.reset_button.isEnabled()

        # save
        reorder_tab.save_button.click()
        assert not reorder_tab.save_button.isEnabled()

        # make a small change
        reorder_tab.targets_input_textarea.setText(valid_target_definition.replace("1", "2"))

        # check buttons again
        assert reorder_tab.save_button.isEnabled()
        assert reorder_tab.reset_button.isEnabled()
        assert not reorder_tab.restore_button.isVisible()
        assert reorder_tab.reorder_button.isEnabled()

        # done
        fm_window.forceClose() # prevent prompt, since changes have been made
        qtbot.waitUntil(lambda: not fm_window.isVisible(), timeout=5_000)
        mw.close()
