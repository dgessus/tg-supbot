import aiosqlite

from utils.paths import Paths
from bin.handlers.logger import logger

import asyncio
from typing import Dict, Tuple, Any

path = Paths()


class _Database:
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            logger.info('creating a new db instance. . .')
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.db_path = path.db_path
        self.connection = None
        self.schema_state = "InitState.NOT_INITIALIZED"
        self.pragma_state = "InitState.NOT_INITIALIZED"
        logger.info('a new db instance created')

    async def _initialize(self):
        logger.info('initializing database. . .')
        self.connection = await aiosqlite.connect(self.db_path)
        self.connection.row_factory = aiosqlite.Row
        self.schema_state = "InitState.INITIALIZATION"
        await self._execute(('''
                CREATE TABLE IF NOT EXISTS tickets (
                user_id INTEGER NOT NULL,
                username TEXT,
                shop_name TEXT,
                message_text TEXT NOT NULL,
                status INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                closed_by TEXT,
                closed_at TEXT,
                designated_dept TEXT,
                assigned_to TEXT,
                media_file_ids TEXT,
                texting_messages TEXT)
                '''))
        logger.info('database initialized')
        self.schema_state = "InitState.RUNNING"
        self.pragma_state = "InitState.INITIALIZATION"
        await self._execute(('''PRAGMA journal_mode=WAL;'''))
        self.pragma_state = "InitState.RUNNING"

    async def _execute(self, query, values: tuple = None, mode: str = None):
        if self.schema_state == "InitState.NOT_INITIALIZED":
            await self._initialize()
            logger.info(f'executing query: <{query}> values: <{values}>')
            cursor = await self.connection.execute(query, values)
            await self.connection.commit()
            return cursor

        elif mode == "write":
            async with _Database._lock:
                try:
                    logger.info(f'executing query: <{query}> values: <{values}>')
                    cursor = await self.connection.execute(query, values)
                    await self.connection.commit()
                    return cursor

                except Exception as e:
                    logger.error(f"an error occurred during database write: <{e}>")
                    raise
        else:
            try:
                logger.info(f'executing query: <{query}> values: <{values}>')
                cursor = await self.connection.execute(query, values)
                await self.connection.commit()
                return cursor

            except Exception as e:
                logger.error(f"an error occurred during database operation: <{e}>")
                raise

    async def insert(self, table, data: dict):
        keys = ', '.join(data.keys())
        placeholders = ', '.join(['?'] * len(data.keys()))
        values = tuple(data.values())
        query = f"INSERT INTO {table} ({keys}) VALUES ({placeholders})"

        cursor = await self._execute(query, values, "write")
        return cursor.lastrowid

    async def select(self, table: str, columns_values: dict[str, tuple]):
        columns = columns_values.keys()
        values = next(iter(columns_values.values()))
        columns_placeholders = ', '.join(columns)
        try:
          values_placeholders = ', '.join('?' * len(values))
        except TypeError:
          values_placeholders = '?'
        query = f"SELECT * FROM {table} WHERE {columns_placeholders} in ({values_placeholders})"
        cursor = await self._execute(query, values)
        return  await cursor.fetchall()

    async def select_range(self, table: str, columns_values: dict[str, tuple]):
        logger.info('executing <select range> command on database. . .')
        if not columns_values:
            raise ValueError("Must supply at least one column")

        conditions = []
        params = []

        for column, (start, end) in columns_values.items():
            if not (start and end):
                raise ValueError(f"Column {column} must have exactly two values for range")
            conditions.append(f"{column} BETWEEN ? AND ?")
            params.extend([start, end])

        query = f"SELECT * FROM {table} WHERE {' AND '.join(conditions)}"
        logger.info(f"query: <{query}>")
        cursor = await self._execute(query, tuple(params))
        logger.info(f"query executed: {cursor} {params}")
        return await cursor.fetchall()

    async def update(self, table: str, match_columns_values: dict, columns_values: dict):
        column_placeholders = ', '.join(f'{column} = ?' for column in columns_values.keys())
        logger.info(f"match_columns_values.keys(): <{match_columns_values.keys()}>")
        match_column_placeholders = ' AND '.join(f'{column} = ?' for column in match_columns_values.keys())
        query = f'UPDATE {table} SET {column_placeholders} WHERE {match_column_placeholders}'
        values = tuple(columns_values.values())
        match_values = tuple(match_columns_values.values())
        values = values + match_values
        await self._execute(query, values, "write")

        return self

