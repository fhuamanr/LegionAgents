"""Small PostgreSQL JSONB document store used by production adapters."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID


class PostgresJsonDocumentStore:
    """Stores typed platform records as JSONB in PostgreSQL."""

    def __init__(self, dsn: str, table_name: str = "platform_documents") -> None:
        self._dsn = dsn
        self._table_name = table_name
        self._pool: Any | None = None
        self._initialized = False

    async def upsert(
        self,
        *,
        bucket: str,
        document_id: UUID | str,
        key: str,
        payload: dict[str, Any],
    ) -> None:
        await self._ensure_initialized()
        async with self._pool.acquire() as connection:
            await connection.execute(
                f"""
                INSERT INTO {self._table_name} (bucket, id, key, payload, updated_at)
                VALUES ($1, $2::uuid, $3, $4::jsonb, $5)
                ON CONFLICT (bucket, id)
                DO UPDATE SET key = EXCLUDED.key, payload = EXCLUDED.payload, updated_at = EXCLUDED.updated_at
                """,
                bucket,
                str(document_id),
                key,
                json.dumps(payload),
                datetime.now(timezone.utc),
            )

    async def get(self, *, bucket: str, document_id: UUID | str) -> dict[str, Any]:
        await self._ensure_initialized()
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(
                f"SELECT payload FROM {self._table_name} WHERE bucket = $1 AND id = $2::uuid",
                bucket,
                str(document_id),
            )
        if row is None:
            raise KeyError(str(document_id))
        return self._decode_payload(row["payload"])

    async def list(
        self,
        *,
        bucket: str,
        key_prefix: str | None = None,
    ) -> tuple[dict[str, Any], ...]:
        await self._ensure_initialized()
        async with self._pool.acquire() as connection:
            if key_prefix is None:
                rows = await connection.fetch(
                    f"SELECT payload FROM {self._table_name} WHERE bucket = $1 ORDER BY key, updated_at",
                    bucket,
                )
            else:
                rows = await connection.fetch(
                    f"""
                    SELECT payload FROM {self._table_name}
                    WHERE bucket = $1 AND key LIKE $2
                    ORDER BY key, updated_at
                    """,
                    bucket,
                    f"{key_prefix}%",
                )
        return tuple(self._decode_payload(row["payload"]) for row in rows)

    async def delete(self, *, bucket: str, document_id: UUID | str) -> None:
        await self._ensure_initialized()
        async with self._pool.acquire() as connection:
            await connection.execute(
                f"DELETE FROM {self._table_name} WHERE bucket = $1 AND id = $2::uuid",
                bucket,
                str(document_id),
            )

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        asyncpg = self._import_asyncpg()
        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=5)
        async with self._pool.acquire() as connection:
            await connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._table_name} (
                    bucket TEXT NOT NULL,
                    id UUID NOT NULL,
                    key TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (bucket, id)
                )
                """
            )
            await connection.execute(
                f"""
                CREATE INDEX IF NOT EXISTS {self._table_name}_bucket_key_idx
                ON {self._table_name} (bucket, key)
                """
            )
        self._initialized = True

    def _import_asyncpg(self) -> Any:
        try:
            import asyncpg  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "PostgreSQL persistence requires asyncpg. Install project requirements before using POSTGRES_DSN."
            ) from exc
        return asyncpg

    def _decode_payload(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, str):
            return json.loads(payload)
        return dict(payload)
