from __future__ import annotations

from pathlib import Path

import pytest

from app.storage.db import Database
from app.storage.repositories import UserRepository


@pytest.mark.asyncio
async def test_list_telegram_ids_returns_saved_users_once(tmp_path: Path) -> None:
    db = Database(tmp_path / "bot.db")
    await db.connect()
    try:
        schema_path = Path(__file__).resolve().parents[2] / "storage" / "migrations" / "001_init.sql"
        await db.init_schema(schema_path)

        users = UserRepository(db)
        await users.get_or_create(3003)
        await users.get_or_create(1001)
        await users.get_or_create(3003)

        assert await users.list_telegram_ids() == [3003, 1001]
    finally:
        await db.close()
