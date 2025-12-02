from __future__ import annotations

from typing import Any, Optional
from frequencyman.lib.addon_config import AddonConfig

def test_addon_config_get():
    config_data = {"key1": "value1", "key2": 2}

    def loader() -> Optional[dict[str, Any]]:
        return config_data

    def saver(data: dict[str, Any]) -> None:
        pass

    config = AddonConfig(loader, saver)
    config.load()

    assert config.get("key3", "default") == "default"
    assert config.get("key3", 123) == 123
