from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass(slots=True)
class DocumentRecord:
    record_id: str
    content: str
    metadata: Dict[str, Any]
    created_at: datetime


class DocumentStore:
    def __init__(self, path: str) -> None:
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, detect_types=sqlite3.PARSE_DECLTYPES)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    collection TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (collection, record_id)
                )
                """
            )
            conn.commit()

    def upsert(
        self,
        collection: str,
        record_id: str,
        content: str,
        metadata: Dict[str, Any],
        created_at: Optional[datetime] = None,
    ) -> None:
        timestamp = (created_at or datetime.utcnow()).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents (collection, record_id, content, metadata, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(collection, record_id) DO UPDATE SET
                    content=excluded.content,
                    metadata=excluded.metadata,
                    created_at=excluded.created_at
                """,
                (collection, record_id, content, json.dumps(metadata), timestamp),
            )
            conn.commit()

    def recent(self, collection: str, limit: int = 10) -> List[DocumentRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT record_id, content, metadata, created_at
                FROM documents
                WHERE collection = ?
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (collection, limit),
            ).fetchall()
        return [
            DocumentRecord(
                record_id=row[0],
                content=row[1],
                metadata=json.loads(row[2]),
                created_at=datetime.fromisoformat(row[3]),
            )
            for row in rows
        ]

    def search(self, collection: str, query: str, limit: int = 5) -> List[DocumentRecord]:
        pattern = f"%{query}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT record_id, content, metadata, created_at
                FROM documents
                WHERE collection = ? AND content LIKE ?
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (collection, pattern, limit),
            ).fetchall()
        return [
            DocumentRecord(
                record_id=row[0],
                content=row[1],
                metadata=json.loads(row[2]),
                created_at=datetime.fromisoformat(row[3]),
            )
            for row in rows
        ]

    def get(self, collection: str, record_id: str) -> Optional[DocumentRecord]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT record_id, content, metadata, created_at
                FROM documents
                WHERE collection = ? AND record_id = ?
                LIMIT 1
                """,
                (collection, record_id),
            ).fetchone()
        if not row:
            return None
        return DocumentRecord(
            record_id=row[0],
            content=row[1],
            metadata=json.loads(row[2]),
            created_at=datetime.fromisoformat(row[3]),
        )

    def count(self, collection: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE collection = ?",
                (collection,),
            ).fetchone()
        return int(row[0]) if row else 0

    def list_all(self, collection: str) -> List[DocumentRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT record_id, content, metadata, created_at
                FROM documents
                WHERE collection = ?
                ORDER BY datetime(created_at) DESC
                """,
                (collection,),
            ).fetchall()
        return [
            DocumentRecord(
                record_id=row[0],
                content=row[1],
                metadata=json.loads(row[2]),
                created_at=datetime.fromisoformat(row[3]),
            )
            for row in rows
        ]

    def delete(self, collection: str, record_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM documents WHERE collection = ? AND record_id = ?",
                (collection, record_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_collection(self, collection: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM documents WHERE collection = ?", (collection,))
            conn.commit()

    def list_collections(self) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT collection FROM documents ORDER BY collection"
            ).fetchall()
        return [row[0] for row in rows]
