from __future__ import annotations

from pathlib import Path
from typing import Any
import asyncio

import aiosqlite


class Database:
    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._db_path.as_posix())
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON;")
        await self._conn.execute("PRAGMA journal_mode = WAL;")
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def init_schema(self, schema_path: Path) -> None:
        schema_sql = schema_path.read_text(encoding="utf-8")
        async with self._lock:
            conn = self._require_conn()
            await conn.executescript(schema_sql)
            await conn.commit()

    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> aiosqlite.Cursor:
        async with self._lock:
            conn = self._require_conn()
            cursor = await conn.execute(sql, params)
            await conn.commit()
            return cursor

    async def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> aiosqlite.Row | None:
        conn = self._require_conn()
        async with conn.execute(sql, params) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[aiosqlite.Row]:
        conn = self._require_conn()
        async with conn.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
        return list(rows)

    def _require_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not connected")
        return self._conn
