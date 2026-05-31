from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.storage.db import Database
from app.storage.models import CredentialRecord
from app.utils import utc_now_iso


class UserRepository:
    def __init__(self, db: Database):
        self._db = db

    async def get_or_create(self, telegram_id: int) -> int:
        row = await self._db.fetchone(
            "SELECT id FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        if row is not None:
            await self._db.execute(
                "UPDATE users SET updated_at = ? WHERE id = ?",
                (utc_now_iso(), row["id"]),
            )
            return int(row["id"])

        now = utc_now_iso()
        cursor = await self._db.execute(
            "INSERT INTO users (telegram_id, created_at, updated_at) VALUES (?, ?, ?)",
            (telegram_id, now, now),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("Failed to create user")
        return int(cursor.lastrowid)


class JobRepository:
    def __init__(self, db: Database):
        self._db = db

    async def create(self, user_id: int, url: str, source: str, status: str = "created") -> int:
        now = utc_now_iso()
        cursor = await self._db.execute(
            """
            INSERT INTO jobs (
                user_id, url, source, status, file_type, file_size, duration, error_code, created_at, updated_at
            ) VALUES (?, ?, ?, ?, NULL, NULL, NULL, NULL, ?, ?)
            """,
            (user_id, url, source, status, now, now),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("Failed to create job")
        return int(cursor.lastrowid)

    async def update_status(
        self,
        job_id: int,
        status: str,
        *,
        file_type: str | None = None,
        file_size: int | None = None,
        duration: int | None = None,
        error_code: str | None = None,
    ) -> None:
        await self._db.execute(
            """
            UPDATE jobs
            SET status = ?, file_type = ?, file_size = ?, duration = ?, error_code = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, file_type, file_size, duration, error_code, utc_now_iso(), job_id),
        )

    async def get(self, job_id: int) -> dict[str, Any] | None:
        row = await self._db.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
        if row is None:
            return None
        return dict(row)


class CredentialStore:
    def __init__(self, db: Database, ttl_days: int):
        self._db = db
        self._ttl_days = ttl_days

    async def save(
        self,
        user_id: int,
        provider: str,
        login: str | None,
        password_or_token: str,
    ) -> None:
        now = datetime.now(tz=UTC)
        expires_at = now + timedelta(days=self._ttl_days)
        now_iso = now.isoformat()
        await self._db.execute(
            """
            INSERT INTO credentials (user_id, provider, login, password_or_token, expires_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, provider)
            DO UPDATE SET
                login = excluded.login,
                password_or_token = excluded.password_or_token,
                expires_at = excluded.expires_at,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                provider,
                login,
                password_or_token,
                expires_at.isoformat(),
                now_iso,
                now_iso,
            ),
        )

    async def get(self, user_id: int, provider: str) -> CredentialRecord | None:
        row = await self._db.fetchone(
            """
            SELECT user_id, provider, login, password_or_token, expires_at
            FROM credentials
            WHERE user_id = ? AND provider = ?
            """,
            (user_id, provider),
        )
        if row is None:
            return None

        expires_at = datetime.fromisoformat(row["expires_at"])
        record = CredentialRecord(
            user_id=int(row["user_id"]),
            provider=str(row["provider"]),
            login=row["login"],
            password_or_token=str(row["password_or_token"]),
            expires_at=expires_at,
        )
        if record.is_expired():
            await self.delete(user_id, provider)
            return None
        return record

    async def delete(self, user_id: int, provider: str) -> None:
        await self._db.execute(
            "DELETE FROM credentials WHERE user_id = ? AND provider = ?",
            (user_id, provider),
        )


class SettingsRepository:
    def __init__(self, db: Database):
        self._db = db

    async def set(self, key: str, value: str) -> None:
        now = utc_now_iso()
        await self._db.execute(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value, now),
        )

    async def get(self, key: str) -> str | None:
        row = await self._db.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        if row is None:
            return None
        return str(row["value"])
