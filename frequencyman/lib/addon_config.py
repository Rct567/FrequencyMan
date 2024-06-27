"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""


from typing import Any, Callable
from aqt import Union

from .utilities import JSON_TYPE

class AddonConfig():

    __config: dict[str, JSON_TYPE]
    __config_writer: Callable[[dict[str, Any]], None]

    def __init__(self, config: dict[str, Any], config_writer: Callable[[dict[str, Any]], None]):
        self.__config = config
        self.__config_writer = config_writer

    def __getitem__(self, key: str) -> JSON_TYPE:
        return self.__config[key]

    def __contains__(self, key: str) -> bool:
        return key in self.__config

    def is_enabled(self, key: str) -> bool:
        if key not in self.__config:
            return False
        val = self.__config[key]
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ["y", "yes", "true"]
        return False

    def update_setting(self, key: str, value: Union[bool, int, float, str, list[Any], dict[str, Any]]) -> None:
        self.__config[key] = value
        self.__config_writer(self.__config)
