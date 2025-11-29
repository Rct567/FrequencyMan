"""
Tests for WordsOverviewTab.
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
    build_target_list,
    build_loaded_config,
    setup_mock_main_window,
    frequencyman_window_creator,
    WordsOverviewTab
)

if TYPE_CHECKING:
    import pytest
    from anki.collection import Collection
    from pytestqt.qtbot import QtBot
    from frequencyman.reorder_logger import ReorderLogger


reorder_logger = reorder_logger_fixture
test_collection = test_collection_fixture


class TestWordsOverviewTab:

    @with_test_collection("two_deck_collection")
    def test_words_overview_tab_options_and_filters(
        self,
        qtbot: QtBot,
        test_collection: Collection,
        reorder_logger: ReorderLogger,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:

        setup_mock_main_window(monkeypatch)

        addon_config = build_loaded_config(build_target_list(test_collection))

        mw = MockAnkiQt(test_collection)
        qtbot.addWidget(mw)

        fm_window = frequencyman_window_creator(mw, addon_config, reorder_logger)
        assert fm_window
        qtbot.addWidget(fm_window)
        qtbot.waitExposed(fm_window)

        # Switch to Words Overview Tab
        fm_window.show_tab(WordsOverviewTab.id)
        words_tab = fm_window.tab_menu_options[WordsOverviewTab.id]
        assert isinstance(words_tab, WordsOverviewTab)

        qtbot.waitUntil(lambda: words_tab.first_paint_event_done, timeout=5_000)
        qtbot.waitUntil(lambda: getattr(words_tab, "target_list", None) is not None, timeout=5_000)

        # 1. Test OVERVIEW_OPTIONS
        for index, option_cls in enumerate(WordsOverviewTab.OVERVIEW_OPTIONS):
            words_tab.overview_options_dropdown.setCurrentIndex(index)
            qtbot.wait(50)

            selected_option_instance = words_tab.overview_options_available[index]
            assert isinstance(selected_option_instance, option_cls)
            assert words_tab.table_label.text() == selected_option_instance.data_description()

            # Verify table has content
            assert words_tab.table.columnCount() > 0
            empty_tables = {'MatureWordsOverview', 'WordUnderexposureOverview', 'WordFamiliaritySweetspotOverview'}
            if not selected_option_instance.__class__.__name__ in empty_tables:
                assert words_tab.table.rowCount() > 1, "Table {} should have rows".format(selected_option_instance.__class__.__name__)

        # 2. Test additional_columns
        # Reset to first option for consistency
        words_tab.overview_options_dropdown.setCurrentIndex(0)
        qtbot.wait(50)

        initial_column_count = words_tab.table.columnCount()
        current_labels = words_tab.overview_options_available[words_tab.selected_overview_option_index].labels()

        for column in words_tab.additional_columns:
            checkbox = words_tab.additional_column_checkboxes[column.title]
            should_hide = column.should_hide(current_labels)

            # Verify checkbox visibility
            assert checkbox.isVisible() == (not should_hide)

            if not checkbox.isChecked():
                checkbox.setChecked(True)
                qtbot.wait(50)

                if not should_hide:
                    # Verify column count increased
                    assert words_tab.table.columnCount() > initial_column_count
                    initial_column_count = words_tab.table.columnCount()
                else:
                    # Verify column count did NOT increase
                    assert words_tab.table.columnCount() == initial_column_count

        # 3. Test filters
        for filter_option in words_tab.filters:
            checkbox = words_tab.filter_checkboxes[filter_option.title]

            # If checkbox is visible and enabled, toggle it
            if checkbox.isVisible() and checkbox.isEnabled():
                original_state = checkbox.isChecked()
                checkbox.setChecked(not original_state)
                qtbot.wait(50)
                checkbox.setChecked(original_state) # Restore
                qtbot.wait(50)

        fm_window.close()
        qtbot.waitUntil(lambda: not fm_window.isVisible(), timeout=5_000)
        mw.close()
