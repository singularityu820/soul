"""
Chat storage with SQLite persistence
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ...schemas import ChatMessage, ChatThreadOut


class ChatStorage:
    """SQLite-based persistent storage for chat threads and messages"""
    
    def __init__(self, db_path: str = "storage/chat.sqlite3"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    thread_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    participants TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    last_message_at REAL NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    language TEXT,
                    emotion_label TEXT,
                    emotion_score REAL,
                    voice_style TEXT,
                    llm_provider TEXT,
                    tts_provider TEXT,
                    audio_reference TEXT,
                    audio_segments TEXT,
                    username TEXT,
                    FOREIGN KEY (thread_id) REFERENCES threads(thread_id)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_thread_id 
                ON messages(thread_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_created_at 
                ON messages(created_at)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_username 
                ON messages(username)
            """)
            
            conn.commit()
    
    def save_thread(
        self,
        thread_id: str,
        title: str,
        participants: List[str],
        created_at: float,
        last_message_at: float,
    ):
        """Save or update a thread"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO threads 
                (thread_id, title, participants, created_at, last_message_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    thread_id,
                    title,
                    json.dumps(participants),
                    created_at,
                    last_message_at,
                ),
            )
            conn.commit()
    
    def get_thread(self, thread_id: str) -> Optional[ChatThreadOut]:
        """Get a thread by ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT thread_id, title, participants, created_at, last_message_at FROM threads WHERE thread_id = ?",
                (thread_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            return ChatThreadOut(
                thread_id=row[0],
                title=row[1],
                participants=json.loads(row[2]),
                created_at=datetime.utcfromtimestamp(row[3]),
                last_message_at=datetime.utcfromtimestamp(row[4]),
            )
    
    def list_threads(self) -> List[ChatThreadOut]:
        """List all threads, newest first"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT thread_id, title, participants, created_at, last_message_at 
                FROM threads 
                ORDER BY last_message_at DESC
                """
            )
            rows = cursor.fetchall()
            
            return [
                ChatThreadOut(
                    thread_id=row[0],
                    title=row[1],
                    participants=json.loads(row[2]),
                    created_at=datetime.utcfromtimestamp(row[3]),
                    last_message_at=datetime.utcfromtimestamp(row[4]),
                )
                for row in rows
            ]
    
    def save_message(self, message: ChatMessage, username: str = None):
        """Save a message"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO messages 
                (message_id, thread_id, role, text, created_at, language,
                 emotion_label, emotion_score, voice_style, llm_provider,
                 tts_provider, audio_reference, audio_segments, username)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.message_id,
                    message.thread_id,
                    message.role,
                    message.text,
                    message.created_at.isoformat(),
                    message.language,
                    message.emotion_label,
                    message.emotion_score,
                    message.voice_style,
                    message.llm_provider,
                    message.tts_provider,
                    message.audio_reference,
                    json.dumps(message.audio_segments) if message.audio_segments else None,
                    username,
                ),
            )
            conn.commit()
    
    def get_messages(self, thread_id: str, limit: int = 100) -> List[ChatMessage]:
        """Get messages for a thread"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT message_id, thread_id, role, text, created_at, language,
                       emotion_label, emotion_score, voice_style, llm_provider,
                       tts_provider, audio_reference, audio_segments
                FROM messages 
                WHERE thread_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (thread_id, limit),
            )
            rows = cursor.fetchall()
            
            return [
                ChatMessage(
                    message_id=row[0],
                    thread_id=row[1],
                    role=row[2],
                    text=row[3],
                    created_at=datetime.fromisoformat(row[4]),
                    language=row[5],
                    emotion_label=row[6],
                    emotion_score=row[7],
                    voice_style=row[8],
                    llm_provider=row[9],
                    tts_provider=row[10],
                    audio_reference=row[11],
                    audio_segments=json.loads(row[12]) if row[12] else None,
                )
                for row in rows
            ]
    
    def update_thread_last_message(self, thread_id: str, timestamp: float):
        """Update the last_message_at timestamp for a thread"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE threads SET last_message_at = ? WHERE thread_id = ?",
                (timestamp, thread_id),
            )
            conn.commit()
    
    def get_recent_messages_by_username(self, username: str, limit: int = 3) -> List[ChatMessage]:
        """Get recent messages for a user by username"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT message_id, thread_id, role, text, created_at, language,
                       emotion_label, emotion_score, voice_style, llm_provider,
                       tts_provider, audio_reference, audio_segments
                FROM messages 
                WHERE username = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (username, limit),
            )
            rows = cursor.fetchall()
            
            return [
                ChatMessage(
                    message_id=row[0],
                    thread_id=row[1],
                    role=row[2],
                    text=row[3],
                    created_at=datetime.fromisoformat(row[4]),
                    language=row[5],
                    emotion_label=row[6],
                    emotion_score=row[7],
                    voice_style=row[8],
                    llm_provider=row[9],
                    tts_provider=row[10],
                    audio_reference=row[11],
                    audio_segments=json.loads(row[12]) if row[12] else None,
                )
                for row in rows
            ]
