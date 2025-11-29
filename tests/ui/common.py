from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, TYPE_CHECKING, Optional
from types import SimpleNamespace

# Setup path to allow importing FrequencyMan
PROJECT_ROOT = Path(__file__).resolve().parents[2]
assert (PROJECT_ROOT / "__init__.py").is_file()
PACKAGE_PARENT = PROJECT_ROOT.parent
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

from aqt.qt import QMainWindow
from frequencyman.lib.addon_config import AddonConfig
from frequencyman.ui import main_window as fm_main_window
from frequencyman.configured_target import ValidConfiguredTarget

if TYPE_CHECKING:
    import pytest
    from collections.abc import Callable
    from anki.collection import Collection
    from frequencyman.reorder_logger import ReorderLogger
    from frequencyman.ui.main_window import FrequencyManMainWindow as FrequencyManMainWindowType
    from frequencyman.ui.reorder_cards_tab import ReorderCardsTab as ReorderCardsTabType
    from frequencyman.ui.words_overview_tab import WordsOverviewTab as WordsOverviewTabType

def geom_stub(*_args: object) -> None:
    return None

class DummyApp:
    def styleSheet(self) -> str:
        return ""

class MockAnkiQt(QMainWindow):
    def __init__(self, col: Collection):
        super().__init__()
        self.col = col
        self.app = DummyApp()

class DummyDialogs:
    def __init__(self):
        self._dialogs: dict[str, list] = {}

    def markClosed(self, name: str) -> None:
        pass

def build_target_list(col: Collection) -> list[ValidConfiguredTarget]:
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

    return [ValidConfiguredTarget(
        scope_query="*",
        notes=[{
            "name": model_name,
            "fields": fields,
        }],
    )]

def build_loaded_config(targets: list[ValidConfiguredTarget]) -> AddonConfig:
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

def setup_mock_main_window(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy_dialogs = DummyDialogs()

    monkeypatch.setattr(
        "frequencyman.ui.main_window.dialogs",
        dummy_dialogs,
    )
    monkeypatch.setattr(
        fm_main_window,
        "restoreGeom",
        geom_stub,
    )
    monkeypatch.setattr(
        fm_main_window,
        "saveGeom",
        geom_stub,
    )
    monkeypatch.setattr(
        "aqt.utils.restoreGeom",
        geom_stub,
    )
    monkeypatch.setattr(
        "aqt.utils.saveGeom",
        geom_stub,
    )
    dummy_pm = SimpleNamespace(profile={})
    monkeypatch.setattr("aqt.mw", SimpleNamespace(pm=dummy_pm), raising=False)

def mock_close_event(a0: Any, fm_window: FrequencyManMainWindowType) -> None:
    if a0 is not None:
        for tab_id, tab_obj in fm_window.tab_menu_options.items():
            if tab_id == 'words_overview':
                 result = tab_obj.on_window_closing() # type: ignore[attr-defined]
                 if result is not None and result == 1:
                     a0.ignore()
                     return
        a0.accept()

# Import FrequencyMan module components from the root __init__.py
# We need to load it as a separate module because 'frequencyman' resolves to the library package
import importlib.util
spec = importlib.util.spec_from_file_location("FrequencyMan_addon", PROJECT_ROOT / "__init__.py")
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load FrequencyMan addon from {PROJECT_ROOT / '__init__.py'}")
FrequencyMan_module = importlib.util.module_from_spec(spec)
sys.modules["FrequencyMan_addon"] = FrequencyMan_module
spec.loader.exec_module(FrequencyMan_module)

frequencyman_window_creator: Callable[[MockAnkiQt, AddonConfig, ReorderLogger], Optional[FrequencyManMainWindowType]] = FrequencyMan_module.frequencyman_window_creator
FrequencyManMainWindow: type[FrequencyManMainWindowType] = FrequencyMan_module.FrequencyManMainWindow
ReorderCardsTab: type[ReorderCardsTabType] = FrequencyMan_module.ReorderCardsTab
WordsOverviewTab: type[WordsOverviewTabType] = FrequencyMan_module.WordsOverviewTab
