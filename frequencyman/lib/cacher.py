import binascii
import hashlib
import json
import os
import sqlite3
from typing import Any, Callable, Optional, TypeVar
from time import time

T = TypeVar('T')


class Cacher:
    def __init__(self, db_file_path: str, save_buffer_limit: int = 10_000) -> None:

        if not os.path.isdir(os.path.dirname(db_file_path)):
            raise ValueError("Directory for db_file_path does not exist!")

        if os.path.isdir(db_file_path):
            raise ValueError("db_file_path is a directory!")

        self._db_file_path = db_file_path
        self.__conn: Optional[sqlite3.Connection] = None
        self._save_buffer: dict[str, tuple[str, int]] = {}
        self._save_buffer_num_limit = save_buffer_limit
        self._pre_loaded_cache: dict[str, Any] = {}
        self._items_preloaded = False

    def _create_table(self) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache_items (
                id BLOB(16) PRIMARY KEY,
                value BLOB,
                created_at INTEGER
            )
        ''')
        conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        if self.__conn is None:
            self.__conn = sqlite3.connect(self._db_file_path)
            self._create_table()
        return self.__conn

    @staticmethod
    def _hash_id_bin(cache_id: str) -> bytes:
        return hashlib.md5(cache_id.encode('utf-8')).digest()

    @staticmethod
    def _hash_id_hex(cache_id: str) -> str:
        return hashlib.md5(cache_id.encode('utf-8')).hexdigest()

    @staticmethod
    def binary_to_hex(binary_data: bytes) -> str:
        return binascii.hexlify(binary_data).decode('utf-8')

    def pre_load_all_items(self) -> None:
        if self._items_preloaded:
            return

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, value FROM cache_items')
        for row in cursor:
            hashed_cache_id = self.binary_to_hex(row[0])
            assert len(hashed_cache_id) == 32
            self._pre_loaded_cache[hashed_cache_id] = json.loads(row[1])
        self._items_preloaded = True

    def num_items_stored(self) -> int:
        if self._save_buffer:
            raise Exception("Cannot call num_items_stored() if save_buffer is not empty")
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM cache_items')
        return cursor.fetchone()[0]

    def get_item(self, cache_id: str, producer: Callable[..., T]) -> T:

        if (hashed_cache_id := self._hash_id_hex(cache_id)) in self._pre_loaded_cache:
            return self._pre_loaded_cache[hashed_cache_id]

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT value, created_at FROM cache_items WHERE id = ?', (self._hash_id_bin(cache_id),))
        row = cursor.fetchone()

        if row:
            return json.loads(row[0])

        result = producer()
        self.save_item(cache_id, result)
        return result

    def delete_item(self, cache_id: str) -> None:

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM cache_items WHERE id = ?', (self._hash_id_bin(cache_id),))
        conn.commit()
        if (hashed_cache_id := self._hash_id_hex(cache_id)) in self._pre_loaded_cache:
            del self._pre_loaded_cache[hashed_cache_id]

    def save_item(self, cache_id: str, value: Any) -> None:
        self._add_to_save_buffer(cache_id, value)
        self._pre_loaded_cache[self._hash_id_hex(cache_id)] = value

    def _add_to_save_buffer(self, cache_id: str, value: Any) -> None:

        timestamp = int(time())
        serialized_value = json.dumps(value)
        self._save_buffer[cache_id] = (serialized_value, timestamp)
        if len(self._save_buffer) >= self._save_buffer_num_limit:
            self.flush_save_buffer()

    def flush_save_buffer(self) -> None:
        if not self._save_buffer:
            return

        conn = self._get_connection()
        cursor = conn.cursor()
        save_buffer_items = ((self._hash_id_bin(id), values[0], values[1]) for id, values in self._save_buffer.items())
        cursor.executemany('''
            INSERT OR REPLACE INTO cache_items (id, value, created_at) VALUES (?, ?, ?)
        ''', save_buffer_items)
        conn.commit()
        self._save_buffer.clear()

    def close(self) -> None:
        self.flush_save_buffer()  # Ensure any buffered data is saved
        if self.__conn is not None:
            self.__conn.close()
            self.__conn = None

    def __del__(self) -> None:
        self.close()
