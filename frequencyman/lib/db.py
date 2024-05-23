"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

import sqlite3
from typing import Any, Optional, Iterable


class QueryResults:

    def __init__(self, cursor: sqlite3.Cursor):
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


class SQLiteDB:

    conn: sqlite3.Connection
    cursor: sqlite3.Cursor

    def __init__(self, **kwargs):
        if 'sqlite_file' in kwargs:
            self.conn = sqlite3.connect(kwargs['sqlite_file'])
        elif 'connection' in kwargs:
            self.conn = kwargs['connection']
        else:
            raise ValueError("You must provide either 'sqlite_file' or 'connection' as a named argument.")
        self.cursor = self.conn.cursor()

    def query(self, table: str, columns: str, condition: str, params: tuple = ()) -> QueryResults:
        query = "SELECT {} FROM {} WHERE {}".format(columns, table, condition)
        self.cursor.execute(query, params)
        return QueryResults(self.cursor)

    def update_data(self, table: str, data: dict[str, Any], condition: str, params: tuple = ()) -> None:
        set_clause = ', '.join([f"{col} = ?" for col in data.keys()])
        query = "UPDATE {} SET {} WHERE {}".format(table, set_clause, condition)
        self.cursor.execute(query, tuple(list(data.values()) + list(params)))
        self.conn.commit()

    def delete_data(self, table: str, condition: str, params: tuple = ()) -> None:
        query = "DELETE FROM {} WHERE {}".format(table, condition)
        self.cursor.execute(query, params)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
