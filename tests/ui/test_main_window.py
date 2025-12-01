"""
Tests for FrequencyManMainWindow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aqt.qt import QTabWidget

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
    FrequencyManMainWindow,
    ReorderCardsTab,
    WordsOverviewTab
)

if TYPE_CHECKING:
    import pytest
    from anki.collection import Collection
    from pytestqt.qtbot import QtBot
    from frequencyman.reorder_logger import ReorderLogger


reorder_logger = reorder_logger_fixture
test_collection = test_collection_fixture


class TestFrequencyManMainWindow:

    @with_test_collection("two_deck_collection")
    def test_frequency_man_main_window_shows_tabs(
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

        assert isinstance(fm_window, FrequencyManMainWindow)
        assert fm_window is not None, "Window creator should return a window instance"

        qtbot.addWidget(fm_window)
        qtbot.waitExposed(fm_window)

        assert (central := fm_window.centralWidget())
        assert (central_layout := central.layout())
        assert central_layout.count() == 1, f"Expected 1 widget in central layout, got {central_layout.count()}"
        assert len(fm_window.findChildren(QTabWidget)) == 1, f"Expected 1 QTabWidget, got {len(fm_window.findChildren(QTabWidget))}"

        # Assert window is visible after being shown
        assert fm_window.isVisible(), "Main window should be visible"

        # Assert window has correct title
        assert "FrequencyMan" in fm_window.windowTitle()

        # Assert tab widget exists and has correct number of tabs (2: reorder + words overview)
        assert fm_window.tab_widget is not None
        assert fm_window.tab_widget.count() == 2, f"Expected 2 tabs, got {fm_window.tab_widget.count()}"

        # Assert tab_menu_options has the expected keys
        assert "main" in fm_window.tab_menu_options
        assert "reorder_cards" in fm_window.tab_menu_options
        assert "words_overview" in fm_window.tab_menu_options

        # Test reorder cards tab
        reorder_tab = fm_window.tab_menu_options["reorder_cards"]
        assert isinstance(reorder_tab, ReorderCardsTab)
        assert reorder_tab.id == "reorder_cards"
        assert reorder_tab.name is not None
        qtbot.waitUntil(lambda: reorder_tab.first_paint_event_done, timeout=5_000)

        assert (reorder_layout := reorder_tab.layout())
        assert reorder_layout.count() == 4, f"Expected 4 widgets in ReorderCardsTab layout, got {reorder_layout.count()}"

        # Assert the reorder tab is the first/current tab initially
        assert fm_window.tab_widget.currentWidget() == reorder_tab, "Reorder tab should be the initial tab"

        # Test words overview tab
        words_tab = fm_window.tab_menu_options[WordsOverviewTab.id]
        assert isinstance(words_tab, WordsOverviewTab)
        assert words_tab.id == "words_overview"
        assert words_tab.name is not None

        # Test tab switching
        fm_window.show_tab(WordsOverviewTab.id)
        assert fm_window.tab_widget.currentWidget() == words_tab, "Words tab should be current after show_tab"

        qtbot.waitUntil(lambda: words_tab.first_paint_event_done, timeout=5_000)
        qtbot.waitUntil(lambda: getattr(words_tab, "target_list", None) is not None, timeout=5_000)

        # Assert target list is properly initialized
        assert hasattr(words_tab, "target_list"), "Words tab should have target_list attribute"
        assert words_tab.target_list.has_targets(), "Target list should have targets"

        # Test switching back to reorder tab
        fm_window.show_tab("reorder_cards")
        assert fm_window.tab_widget.currentWidget() == reorder_tab, "Reorder tab should be current after switching back"

        fm_window.close()
        qtbot.waitUntil(lambda: not fm_window.isVisible(), timeout=5_000)
        assert not fm_window.isVisible(), "Window should be hidden after close"
        mw.close()
