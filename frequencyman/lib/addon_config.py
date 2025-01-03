"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""


from typing import Any, Callable, Optional, Union
from aqt.main import AnkiQt

from .utilities import JSON_TYPE


class AddonConfig():

    __config: Optional[dict[str, JSON_TYPE]]
    __config_load: Callable[[], Optional[dict[str, Any]]]
    __config_save: Callable[[dict[str, Any]], None]

    def __init__(self, config_loader: Callable[[], Optional[dict[str, Any]]], config_saver: Callable[[dict[str, Any]], None]):
        self.__config = None
        self.__config_load = config_loader
        self.__config_save = config_saver

    def load(self) -> None:
        if self.__config is not None:
            raise ValueError("Config already loaded!")
        config = self.__config_load()
        if config is None:
            config = {}
        self.__config = config

    def reload(self) -> None:
        self.__config = None
        self.load()

    def __getitem__(self, key: str) -> JSON_TYPE:
        if self.__config is None:
            raise ValueError("Config not loaded!")
        return self.__config[key]

    def __contains__(self, key: str) -> bool:
        if self.__config is None:
            raise ValueError("Config not loaded!")
        return key in self.__config

    def is_enabled(self, key: str) -> bool:
        if self.__config is None:
            raise ValueError("Config not loaded!")
        if key not in self.__config:
            return False
        val = self.__config[key]
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ["y", "yes", "true"]
        return False

    def update_setting(self, key: str, value: Union[bool, int, float, str, list[Any], dict[str, Any]]) -> None:
        if self.__config is None:
            raise ValueError("Config not loaded!")
        self.__config[key] = value
        self.__config_save(self.__config)

    @staticmethod
    def from_anki_main_window(mw: AnkiQt) -> 'AddonConfig':

        addon_manager = mw.addonManager
        config_loader: Callable[[], Optional[dict[str, Any]]] = lambda: addon_manager.getConfig(__name__)
        config_saver: Callable[[dict[str, Any]], None] = lambda config: addon_manager.writeConfig(__name__, config)

        addon_config = AddonConfig(config_loader, config_saver)
        addon_config.load()
        return addon_config
