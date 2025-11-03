"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""


import binascii
from enum import Enum
import hashlib
import json
from typing import Any, Callable, Optional, TypeVar
from time import time

from .sql_db_file import SqlDbFile

T = TypeVar('T')


class SerializationType(Enum):
    JSON = 0
    STR = 1
    LIST_STR = 2


class PersistentCacher():

    db: SqlDbFile

    def __init__(self, db: SqlDbFile, save_buffer_limit: int = 10_000) -> None:

        self.db = db
        self.db.on_connect(self.__on_db_connect)
        self.db.on_close(self.__on_db_close)

        self._save_buffer: dict[str, tuple[str, SerializationType, int]] = {}
        self._save_buffer_num_limit = save_buffer_limit
        self._pre_loaded_cache: dict[str, Any] = {}
        self._items_preloaded = False


    def __on_db_connect(self) -> None:
        self.db.query('''
            CREATE TABLE IF NOT EXISTS cache_items (
                id BLOB(16) PRIMARY KEY,
                value TEXT,
                storage_type INTEGER,
                created_at INTEGER
            )
        ''')
        self.db.commit()

    @staticmethod
    def _hash_id_bin(cache_id: str) -> bytes:
        return hashlib.md5(cache_id.encode('utf-8')).digest()

    @staticmethod
    def _hash_id_hex(cache_id: str) -> str:
        return hashlib.md5(cache_id.encode('utf-8')).hexdigest()

    @staticmethod
    def binary_to_hex(binary_data: bytes) -> str:
        return binascii.hexlify(binary_data).decode('utf-8')

    @staticmethod
    def deserialize(value: str, storage_type: SerializationType) -> Any:
        if storage_type == SerializationType.LIST_STR:
            return value.split("\x1C")
        elif storage_type == SerializationType.JSON:
            return json.loads(value)
        elif storage_type == SerializationType.STR:
            return value
        else:
            raise Exception("Invalid storage_type!")

    @staticmethod
    def serialize(value: Any, storage_type: SerializationType) -> str:
        if storage_type == SerializationType.LIST_STR:
            return "\x1C".join(value)
        elif storage_type == SerializationType.STR:
            return value
        elif storage_type == SerializationType.JSON:
            return json.dumps(value)
        else:
            raise Exception("Invalid storage_type!")

    @staticmethod
    def auto_serialize(value: Any) -> tuple[str, SerializationType]:
        if isinstance(value, str):
            storage_type = SerializationType.STR
        elif isinstance(value, list) and len(value) > 0 and all(isinstance(item, str) for item in value):
            storage_type = SerializationType.LIST_STR
        else:
            storage_type = SerializationType.JSON

        return (PersistentCacher.serialize(value, storage_type), storage_type)

    def pre_load_all_items(self) -> None:
        if self._items_preloaded:
            return

        result = self.db.query('SELECT id, value, storage_type FROM cache_items')
        for row in result.fetch_rows():
            hashed_cache_id = self.binary_to_hex(row['id'])
            assert len(hashed_cache_id) == 32
            self._pre_loaded_cache[hashed_cache_id] = PersistentCacher.deserialize(row['value'], SerializationType(row['storage_type']))
        self._items_preloaded = True

    def num_items_stored(self) -> int:
        if self._save_buffer:
            raise Exception("Cannot call num_items_stored() if save_buffer is not empty")
        return self.db.count_rows("cache_items")

    def get_item(self, cache_id: str, producer: Callable[..., T]) -> T:

        if (hashed_cache_id := self._hash_id_hex(cache_id)) in self._pre_loaded_cache:
            return self._pre_loaded_cache[hashed_cache_id]

        result = self.db.query('SELECT value, storage_type, created_at FROM cache_items WHERE id = ?', self._hash_id_bin(cache_id))
        row = result.fetch_row()

        if row:
            return PersistentCacher.deserialize(row['value'], SerializationType(row['storage_type']))

        result = producer()
        self.save_item(cache_id, result)
        return result

    def delete_item(self, cache_id: str) -> None:
        self.db.delete_row('cache_items', 'id = ?', self._hash_id_bin(cache_id))
        self.db.commit()
        if (hashed_cache_id := self._hash_id_hex(cache_id)) in self._pre_loaded_cache:
            del self._pre_loaded_cache[hashed_cache_id]

    def save_item(self, cache_id: str, value: Any) -> None:
        self._add_to_save_buffer(cache_id, value)
        self._pre_loaded_cache[self._hash_id_hex(cache_id)] = value

    def _add_to_save_buffer(self, cache_id: str, value: Any) -> None:

        timestamp = int(time())
        serialized_value, storage_type = PersistentCacher.auto_serialize(value)
        self._save_buffer[cache_id] = (serialized_value, storage_type, timestamp)
        if len(self._save_buffer) >= self._save_buffer_num_limit:
            self.flush_save_buffer()

    def clear_pre_loaded_cache(self) -> None:
        self._pre_loaded_cache.clear()

    def flush_save_buffer(self) -> None:
        if not self._save_buffer:
            return

        save_buffer_items = ((self._hash_id_bin(id), values[0], values[1].value, values[2]) for id, values in self._save_buffer.items())
        self.db.query_many('''
            INSERT OR REPLACE INTO cache_items (id, value, storage_type, created_at) VALUES (?, ?, ?, ?)
        ''', save_buffer_items)
        self.db.commit()

        self._save_buffer.clear()
        self.clear_pre_loaded_cache()

    def __on_db_close(self) -> None:
        self.flush_save_buffer()

    def close(self) -> None:
        self.db.close()
