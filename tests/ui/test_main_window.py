"""
Tests for FrequencyManMainWindow.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TYPE_CHECKING

from anki.errors import InvalidInput
from aqt.qt import QMainWindow
from tests.tools import (
    reorder_logger as reorder_logger_fixture,
    test_collection as test_collection_fixture,
    with_test_collection,
)

from frequencyman.lib.addon_config import AddonConfig
from frequencyman.target_list import TargetList, JsonTargetsResult
from frequencyman.ui import main_window as fm_main_window

PROJECT_ROOT = Path(__file__).resolve().parents[2]
assert (PROJECT_ROOT / "__init__.py").is_file()
PACKAGE_PARENT = PROJECT_ROOT.parent
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

FrequencyMan_module = importlib.import_module("FrequencyMan")
frequencyman_window_creator = FrequencyMan_module.frequencyman_window_creator
FrequencyManMainWindow = FrequencyMan_module.FrequencyManMainWindow
ReorderCardsTab = FrequencyMan_module.ReorderCardsTab
WordsOverviewTab = FrequencyMan_module.WordsOverviewTab


if TYPE_CHECKING:
    import pytest
    from anki.collection import Collection
    from pytestqt.qtbot import QtBot
    from frequencyman.reorder_logger import ReorderLogger
    from frequencyman.language_data import LanguageData

reorder_logger = reorder_logger_fixture
test_collection = test_collection_fixture


def _geom_stub(*_args: object) -> None:
    return None


class DummyApp:
    def styleSheet(self) -> str:
        return ""


class MockAnkiQt(QMainWindow):
    def __init__(self, col: Collection):
        super().__init__()
        self.col = col
        self.app = DummyApp()


def _build_target_list(col: Collection) -> list[dict[str, Any]]:
    deck_name = col.decks.current()['name']
    model = col.models.current()
    model_name = model['name']
    field_names = [field['name'] for field in model['flds']]

    lang_cycle = ("en", "es")
    fields: dict[str, str] = {}
    for index, field_name in enumerate(field_names):
        fields[field_name] = lang_cycle[index % len(lang_cycle)]
        if index == 1:
            break

    if not fields:
        raise ValueError("No fields available on current model.")

    return [{
        "id": "test_target",
        "deck": deck_name,
        "notes": [{
            "name": model_name,
            "fields": fields,
        }],
    }]


def _build_loaded_config(targets: list[dict[str, Any]]) -> AddonConfig:
    config_store: dict[str, Any] = {
        "reorder_target_list": targets,
        "log_reorder_events": False,
    }

    def loader() -> dict[str, Any]:
        return config_store

    def saver(new_config: dict[str, Any]) -> None:
        config_store.clear()
        config_store.update(new_config)

    addon_config = AddonConfig(loader, saver)
    addon_config.load()
    return addon_config


class TestFrequencyManMainWindow:

    @with_test_collection("two_deck_collection")
    def test_frequency_man_main_window_shows_tabs(
        self,
        qtbot: QtBot,
        test_collection: Collection,
        reorder_logger: ReorderLogger,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        class DummyDialogs:
            def __init__(self):
                self._dialogs: dict[str, list] = {}

            def markClosed(self, name: str) -> None:
                # Mock implementation that doesn't fail - just do nothing
                pass

        dummy_dialogs = DummyDialogs()

        # Patch dialogs in the main_window module where it's imported
        monkeypatch.setattr(
            "frequencyman.ui.main_window.dialogs",
            dummy_dialogs,
        )
        monkeypatch.setattr(
            fm_main_window,
            "restoreGeom",
            _geom_stub,
        )
        monkeypatch.setattr(
            fm_main_window,
            "saveGeom",
            _geom_stub,
        )
        monkeypatch.setattr(
            "aqt.utils.restoreGeom",
            _geom_stub,
        )
        monkeypatch.setattr(
            "aqt.utils.saveGeom",
            _geom_stub,
        )
        assert fm_main_window.restoreGeom.__name__ == "_geom_stub"
        dummy_pm = SimpleNamespace(profile={})
        monkeypatch.setattr("aqt.mw", SimpleNamespace(pm=dummy_pm), raising=False)

        # Cache target validation results to handle async Qt events that may occur after collection is closed
        original_get_targets = TargetList.get_targets_from_json
        cached_result: JsonTargetsResult | None = None

        def safe_get_targets(json_data: str, col: Collection, language_data: LanguageData) -> JsonTargetsResult:  # type: ignore[override]
            nonlocal cached_result
            try:
                result = original_get_targets(json_data, col, language_data)
                cached_result = result
                return result
            except InvalidInput:
                if cached_result is None:
                    raise
                return cached_result

        monkeypatch.setattr(TargetList, "get_targets_from_json", staticmethod(safe_get_targets))

        addon_config = _build_loaded_config(_build_target_list(test_collection))

        mw = MockAnkiQt(test_collection)
        qtbot.addWidget(mw)

        fm_window = frequencyman_window_creator(mw, addon_config, reorder_logger)

        assert isinstance(fm_window, FrequencyManMainWindow)
        assert fm_window is not None, "Window creator should return a window instance"

        qtbot.addWidget(fm_window)
        qtbot.waitExposed(fm_window)

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

        # Override closeEvent to avoid dialogs.markClosed issues

        def mock_close_event(a0): # type: ignore
            if a0 is not None:
                for tab in fm_window.tab_widget.findChildren(type(list(fm_window.tab_menu_options.values())[1])):
                    result = tab.on_window_closing()
                    if result is not None and result == 1:
                        a0.ignore()
                        return
                a0.accept()

        fm_window.closeEvent = mock_close_event
        fm_window.close()
        qtbot.waitUntil(lambda: not fm_window.isVisible(), timeout=5_000)
        assert not fm_window.isVisible(), "Window should be hidden after close"
        mw.close()
