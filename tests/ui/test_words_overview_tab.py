"""
Tests for WordsOverviewTab.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TYPE_CHECKING, Optional

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

if TYPE_CHECKING:
    import pytest
    from collections.abc import Callable
    from anki.collection import Collection
    from pytestqt.qtbot import QtBot
    from frequencyman.reorder_logger import ReorderLogger
    from frequencyman.language_data import LanguageData
    from frequencyman.ui.main_window import FrequencyManMainWindow as FrequencyManMainWindowType
    from frequencyman.ui.reorder_cards_tab import ReorderCardsTab as ReorderCardsTabType
    from frequencyman.ui.words_overview_tab import WordsOverviewTab as WordsOverviewTabType


FrequencyManMainWindow: type[FrequencyManMainWindowType]
frequencyman_window_creator: Callable[[MockAnkiQt, AddonConfig, ReorderLogger], Optional[FrequencyManMainWindowType]]
ReorderCardsTab: type[ReorderCardsTabType]
WordsOverviewTab: type[WordsOverviewTabType]

# import from __init__.py
FrequencyMan_module = importlib.import_module("FrequencyMan")
frequencyman_window_creator = FrequencyMan_module.frequencyman_window_creator
FrequencyManMainWindow = FrequencyMan_module.FrequencyManMainWindow
ReorderCardsTab = FrequencyMan_module.ReorderCardsTab
WordsOverviewTab = FrequencyMan_module.WordsOverviewTab


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


class TestWordsOverviewTab:

    @with_test_collection("two_deck_collection")
    def test_words_overview_tab_options_and_filters(
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
                pass

        dummy_dialogs = DummyDialogs()

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
        dummy_pm = SimpleNamespace(profile={})
        monkeypatch.setattr("aqt.mw", SimpleNamespace(pm=dummy_pm), raising=False)

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

            # Verify table has content or at least headers
            assert words_tab.table.columnCount() > 0

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

        # Override closeEvent to avoid dialogs.markClosed issues
        def mock_close_event(a0): # type: ignore
            if a0 is not None:
                for tab in fm_window.tab_widget.findChildren(type(list(fm_window.tab_menu_options.values())[1])):
                    result = tab.on_window_closing() # type: ignore
                    if result is not None and result == 1:
                        a0.ignore()
                        return
                a0.accept()

        fm_window.closeEvent = mock_close_event # type: ignore[method-assign]
        fm_window.close()
        qtbot.waitUntil(lambda: not fm_window.isVisible(), timeout=5_000)
        mw.close()
