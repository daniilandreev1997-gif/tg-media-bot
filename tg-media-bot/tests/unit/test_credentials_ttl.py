from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.storage.db import Database
from app.storage.repositories import CredentialStore, UserRepository


@pytest.mark.asyncio
async def test_expired_credentials_not_returned_and_deleted(tmp_path: Path) -> None:
    db = Database(tmp_path / "bot.db")
    await db.connect()
    try:
        schema_path = Path(__file__).resolve().parents[2] / "storage" / "migrations" / "001_init.sql"
        await db.init_schema(schema_path)

        users = UserRepository(db)
        creds = CredentialStore(db, ttl_days=7)
        user_id = await users.get_or_create(123456)

        await creds.save(user_id=user_id, provider="vk", login="u", password_or_token="p")
        expired_at = (datetime.now(tz=UTC) - timedelta(days=1)).isoformat()
        await db.execute(
            "UPDATE credentials SET expires_at = ? WHERE user_id = ? AND provider = ?",
            (expired_at, user_id, "vk"),
        )

        record = await creds.get(user_id=user_id, provider="vk")
        assert record is None

        row = await db.fetchone(
            "SELECT 1 FROM credentials WHERE user_id = ? AND provider = ?",
            (user_id, "vk"),
        )
        assert row is None
    finally:
        await db.close()
