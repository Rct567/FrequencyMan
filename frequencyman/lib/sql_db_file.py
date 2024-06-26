"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""


import os
import sqlite3
from typing import Any, Iterable, Optional, Sequence

from .utilities import var_dump, var_dump_log


class QueryResults:

    def __init__(self, connection: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        self.connection = connection
        self.cursor = cursor

    def fetch_row(self) -> Optional[dict[str, Any]]:
        row = self.cursor.fetchone()
        if row:
            return {col[0]: value for col, value in zip(self.cursor.description, row)}

    def fetch_rows(self) -> Iterable[dict[str, Any]]:
        for row in self.cursor:
            yield {col[0]: value for col, value in zip(self.cursor.description, row)}

    def row_count(self) -> int:
        return self.cursor.rowcount
        # return len(list(self.get_rows()))

    def get_last_insert_id(self) -> int:
        if not self.cursor.lastrowid:
            raise Exception("No lastrowid for query!")
        return self.cursor.lastrowid


class SqlDbFile():

    __connection: Optional[sqlite3.Connection] = None
    db_file_path: str

    def __init__(self, db_file_path: str) -> None:
        self.db_file_path = db_file_path

        if not os.path.isdir(os.path.dirname(db_file_path)):
            raise ValueError("Directory for db_file_path {} does not exist!".format(db_file_path))

        if os.path.isdir(db_file_path):
            raise ValueError("db_file_path {} is a directory, not a file!".format(db_file_path))

        if os.path.exists(db_file_path):
            if not os.access(db_file_path, os.R_OK | os.W_OK):
                raise ValueError("db_file_path {} is not readable or writeable!".format(db_file_path))

    def _create_tables(self) -> None:
        raise NotImplementedError()

    def connection(self) -> sqlite3.Connection:
        if self.__connection is None:
            self.__connection = sqlite3.connect(self.db_file_path)
            self._create_tables()
        return self.__connection

    def cursor(self) -> sqlite3.Cursor:
        return self.connection().cursor()

    def commit(self) -> None:

        if self.__connection is None:
            raise Exception("No connection to commit!")

        self.__connection.commit()

    def query(self, query: str, params: Optional[Sequence] = None) -> QueryResults:
        cursor = self.cursor()
        if params:
           cursor.execute(query, params)
        else:
            cursor.execute(query)
        return QueryResults(self.connection(), cursor)

    def query_many(self, query: str, params: Iterable[Sequence]) -> QueryResults:
        cursor = self.cursor()
        cursor.executemany(query, params)
        return QueryResults(self.connection(), cursor)

    def result(self, query: str, params: Optional[Sequence] = None) -> Any:
        result = self.query(query, params)
        row = result.fetch_row()
        if not row:
            raise Exception("No row returned for query '{}'!".format(query))
        first_value = next(iter(row.values()))
        return first_value

    def delete_row(self, table_name: str, where: str, params: Optional[Sequence] = None) -> int:

        result = self.query("DELETE FROM {} WHERE {}".format(table_name, where), params)
        return result.row_count()

    def count_rows(self, table_name: str) -> int:

        if self.__connection is None and not os.path.exists(self.db_file_path):
            return 0

        return self.result("SELECT COUNT(*) FROM {}".format(table_name))

    def close(self) -> None:
        if self.__connection is not None:
            self.__connection.close()
            self.__connection = None

    def __del__(self) -> None:
        self.close()
