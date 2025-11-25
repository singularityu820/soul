"""
Lightweight storage for realtime transcripts.

This keeps realtime voice transcripts separate from the main chat storage
so that saving them does not accidentally trigger ChatService/agent workflows.
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any


class RealtimeTranscriptStorage:
    def __init__(self, db_path: str = "storage/realtime_transcripts.sqlite3") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS realtime_transcripts (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    username TEXT,
                    metadata TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_realtime_session_id ON realtime_transcripts(session_id)"
            )
            # ensure username column exists for older DBs
            cursor = conn.execute("PRAGMA table_info(realtime_transcripts)")
            cols = [r[1] for r in cursor.fetchall()]
            if "username" not in cols:
                try:
                    conn.execute("ALTER TABLE realtime_transcripts ADD COLUMN username TEXT")
                except Exception:
                    # some SQLite versions / states may not allow ALTER TABLE in place; ignore
                    pass
            conn.commit()

    def save_transcript(self, id: str, session_id: str, role: str, text: str, metadata: Optional[Dict[str, Any]] = None):
        username = None
        if metadata and isinstance(metadata, dict):
            username = metadata.get("username")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO realtime_transcripts
                (id, session_id, role, text, created_at, username, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    id,
                    session_id,
                    role,
                    text,
                    datetime.utcnow().isoformat(),
                    username,
                    json.dumps(metadata) if metadata else None,
                ),
            )
            conn.commit()

    def get_transcripts(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT id, session_id, role, text, created_at, metadata
                FROM realtime_transcripts
                WHERE session_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (session_id, limit),
            )
            rows = cursor.fetchall()
            result = []
            for row in rows:
                meta = json.loads(row[5]) if row[5] else None
                result.append({
                    "id": row[0],
                    "session_id": row[1],
                    "role": row[2],
                    "text": row[3],
                    "created_at": row[4],
                    "metadata": meta,
                })
            return result

    def get_transcripts_by_username(self, username: str, limit: int = 100) -> List[Dict[str, Any]]:
        """返回指定用户名的最近实时转录（按 created_at 降序）。

        这里简单使用 metadata 的字符串匹配，因为 metadata 存储为 JSON 文本。
        """
        with sqlite3.connect(self.db_path) as conn:
            # 首先尝试使用 username 列做精确匹配（优先）
            cursor = conn.execute(
                """
                SELECT id, session_id, role, text, created_at, metadata
                FROM realtime_transcripts
                WHERE username = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (username, limit),
            )
            rows = cursor.fetchall()

            # 如果没有通过 username 列命中（例如旧数据或写入时未携带 cookie），
            # 回退到在 metadata JSON 文本中进行字符串匹配的方案以提高兼容性。
            if not rows:
                # 两种常见 JSON 格式："username":"bob" 或 "username": "bob"
                like1 = '%"username":"' + username + '"%'
                like2 = '%"username": "' + username + '"%'
                cursor = conn.execute(
                    """
                    SELECT id, session_id, role, text, created_at, metadata
                    FROM realtime_transcripts
                    WHERE metadata LIKE ? OR metadata LIKE ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (like1, like2, limit),
                )
                rows = cursor.fetchall()

            result = []
            for row in rows:
                meta = json.loads(row[5]) if row[5] else None
                result.append({
                    "id": row[0],
                    "session_id": row[1],
                    "role": row[2],
                    "text": row[3],
                    "created_at": row[4],
                    "metadata": meta,
                })
            return result
