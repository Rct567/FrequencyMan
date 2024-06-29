"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""


import os
import sqlite3
from typing import Any, Iterable, Optional, Sequence

from aqt import Union

from .utilities import var_dump, var_dump_log

QueryParameters = Union[Sequence[Union[int, float, str, bytes]], int, float, str, bytes]

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

    def query(self, query: str, params: Optional[QueryParameters] = None) -> QueryResults:
        cursor = self.cursor()

        if isinstance(params, str) or isinstance(params, int) or isinstance(params, float) or isinstance(params, bytes):
            params = (params,)

        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return QueryResults(self.connection(), cursor)

    def query_many(self, query: str, params: Iterable[Sequence]) -> QueryResults:
        cursor = self.cursor()
        cursor.executemany(query, params)
        return QueryResults(self.connection(), cursor)

    def result(self, query: str, params: Optional[QueryParameters] = None) -> Any:
        result = self.query(query, params)
        row = result.fetch_row()
        if not row:
            raise Exception("No row returned for query '{}'!".format(query))
        first_value = next(iter(row.values()))
        return first_value

    def create_table(self, table_name: str, columns: dict[str, str], constraints: Optional[str] = None) -> QueryResults:
        columns_def = ', '.join('{} {}'.format(name, type_) for name, type_ in columns.items())
        if constraints:
            columns_def += ', ' + constraints
        return self.query('CREATE TABLE IF NOT EXISTS {} ({})'.format(table_name, columns_def))

    def create_index(self, table_name: str, index_name: str, columns: list[str]) -> QueryResults:
        return self.query('CREATE INDEX IF NOT EXISTS {} ON {} ({})'.format(index_name, table_name, ', '.join(columns)))

    def delete_row(self, table_name: str, where: str, params: Optional[QueryParameters] = None) -> int:

        result = self.query("DELETE FROM {} WHERE {}".format(table_name, where), params)
        return result.row_count()

    def count_rows(self, table_name: str) -> int:

        if self.__connection is None and not os.path.exists(self.db_file_path):
            return 0

        return self.result("SELECT COUNT(*) FROM {}".format(table_name))

    def insert_row(self, table_name: str, row: dict[str, Any]) -> QueryResults:
        columns = ', '.join(row.keys())
        placeholders = ', '.join('?' for _ in row)
        query = 'INSERT INTO {} ({}) VALUES ({})'.format(table_name, columns, placeholders)
        params = tuple(row.values())
        return self.query(query, params)

    def insert_many_rows(self, table_name: str, rows: Iterable[dict[str, Any]]) -> QueryResults:
        iterator = iter(rows)
        first_row = next(iterator, None)
        if first_row is None:
            raise Exception("No rows to insert!")

        columns = ', '.join(first_row.keys())
        placeholders = ', '.join('?' for _ in first_row)
        query = 'INSERT INTO {} ({}) VALUES ({})'.format(table_name, columns, placeholders)

        params = [tuple(first_row.values())]
        for row in iterator:
            params.append(tuple(row.values()))

        return self.query_many(query, params)

    def in_transaction(self) -> bool:
        if self.__connection is not None:
            return self.__connection.in_transaction
        return False

    def close(self) -> None:
        if self.__connection is not None:
            if self.__connection.in_transaction:
                raise Exception("Cannot close connection while in transaction!")
            self.__connection.close()
            self.__connection = None

    def __del__(self) -> None:
        self.close()
