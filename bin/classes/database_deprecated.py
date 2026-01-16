import sqlite3

from utils.paths import Paths

import warnings

path = Paths()


warnings.warn(
    "database.py is deprecated. Use aiodatabase.py instead.",
    DeprecationWarning,
    stacklevel=2
)

class _Database:
    def __init__(self):
        self.db_path = path.db_path
        self._initialize()

    def _connect(self):
        connect = sqlite3.connect(self.db_path)
        connect.row_factory = sqlite3.Row
        return connect

    def _initialize(self):
        with self._connect() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tickets (
                    user_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    shop_name TEXT,
                    message_text TEXT NOT NULL,
                    status INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    closed_by TEXT,
                    designated_dept TEXT,
                    assigned_to TEXT),
                    media_file_ids TEXT,
                    ''')

        conn.commit()

    def get_columns(self, table):
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(f"PRAGMA table_info({table})")
            rows = cursor.fetchall()
            return [row["name"] for row in rows]

    def insert(self, table, data: dict):
        with self._connect() as connection:
            keys = ', '.join(data.keys())
            placeholders = ', '.join(['?'] * len(data.keys()))
            values = tuple(data.values())

            query = f"INSERT INTO {table} ({keys}) VALUES ({placeholders})"
            cursor = connection.cursor()
            cursor.execute(query, values)
            connection.commit()
            return cursor.lastrowid

    def select(self, table: str, target_column: str, key: int | str):
        with self._connect() as connection:
            columns = ', '.join(self.get_columns(table))
            query = f"SELECT {columns} FROM {table} WHERE {target_column} = ?"
            cursor = connection.cursor()
            cursor.execute(query, (key,))
            return cursor.fetchall()[-1]

    def update(self, table: str, match_column, match_value, column: str, value):
        with self._connect() as connection:
            query = f"UPDATE {table} SET {column} = ? WHERE {match_column} = ?"
            connection.execute(query, (value, match_value))
            connection.commit()
            return self
